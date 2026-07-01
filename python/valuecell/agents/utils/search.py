from __future__ import annotations

import os
import re
from typing import Any

import aiohttp
from agno.agent import Agent
from loguru import logger

from valuecell.utils.model import create_model_with_provider

PRIMARY_SEARCH_PROVIDER = "tavily"
OPENAI_COMPATIBLE_PROVIDER = "openai-compatible"
FALLBACK_PROVIDER = "openrouter"
FALLBACK_MODEL_ID = "perplexity/sonar"
UNAVAILABLE_MARKER = "SEARCH_UNAVAILABLE"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_TIMEOUT_S = 30

_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)


def _has_source_urls(text: str) -> bool:
    return bool(_URL_PATTERN.search(text))


def _build_search_prompt(query: str) -> str:
    return (
        "Search the web for the user's request using real-time, source-grounded information. "
        "Return concise factual results with explicit source URLs and publication or event dates whenever available. "
        f"If you cannot access real-time web results or cannot provide any URLs, respond exactly with {UNAVAILABLE_MARKER}.\n\n"
        f"Query: {query}"
    )


def _extract_content(response) -> str:
    content = getattr(response, "content", None)
    if content is None:
        content = response
    if isinstance(content, str):
        return content.strip()
    return str(content).strip()


def _format_tavily_result(data: dict[str, Any]) -> str:
    parts: list[str] = []

    answer = str(data.get("answer") or "").strip()
    if answer:
        parts.append(f"Answer:\n{answer}")

    results = data.get("results") or []
    if isinstance(results, list):
        formatted_items: list[str] = []
        for index, item in enumerate(results, start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "Untitled").strip()
            url = str(item.get("url") or "").strip()
            content = str(item.get("content") or item.get("raw_content") or "").strip()
            published_date = str(
                item.get("published_date") or item.get("publishedDate") or ""
            ).strip()

            if not url:
                continue

            line_parts = [f"{index}. {title}", f"URL: {url}"]
            if published_date:
                line_parts.append(f"Date: {published_date}")
            if content:
                line_parts.append(f"Summary: {content}")
            formatted_items.append("\n".join(line_parts))

        if formatted_items:
            parts.append("Sources:\n" + "\n\n".join(formatted_items))

    text = "\n\n".join(parts).strip()
    if not text:
        raise RuntimeError("empty Tavily response")
    if not _has_source_urls(text):
        raise RuntimeError("Tavily response did not include source URLs")
    return text


async def _post_tavily(payload: dict[str, Any], api_key: str, use_bearer: bool) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    request_payload = dict(payload)
    if use_bearer:
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        request_payload["api_key"] = api_key

    timeout = aiohttp.ClientTimeout(total=TAVILY_TIMEOUT_S)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            TAVILY_SEARCH_URL,
            json=request_payload,
            headers=headers,
        ) as response:
            text = await response.text()
            if response.status >= 400:
                raise RuntimeError(f"Tavily HTTP {response.status}: {text[:500]}")
            try:
                data = await response.json()
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"Invalid Tavily JSON response: {text[:500]}") from exc
            if not isinstance(data, dict):
                raise RuntimeError("Invalid Tavily response shape")
            return data


async def _run_tavily_search(query: str) -> str:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY credentials unavailable")

    max_results_raw = os.getenv("TAVILY_MAX_RESULTS", "8").strip()
    try:
        max_results = max(1, min(int(max_results_raw), 20))
    except ValueError:
        max_results = 8

    payload: dict[str, Any] = {
        "query": query,
        "search_depth": os.getenv("TAVILY_SEARCH_DEPTH", "basic"),
        "topic": os.getenv("TAVILY_SEARCH_TOPIC", "general"),
        "max_results": max_results,
        "include_answer": True,
        "include_raw_content": False,
    }

    try:
        data = await _post_tavily(payload, api_key, use_bearer=True)
    except Exception as bearer_exc:  # noqa: BLE001
        logger.warning("Tavily bearer auth failed, retrying legacy body auth: {}", bearer_exc)
        data = await _post_tavily(payload, api_key, use_bearer=False)

    return _format_tavily_result(data)


async def _run_model_search(provider: str, model_id: str | None, prompt: str) -> str:
    model = create_model_with_provider(
        provider=provider,
        model_id=model_id,
        max_tokens=None,
    )
    response = await Agent(model=model, markdown=False).arun(prompt)
    content = _extract_content(response)
    if not content:
        raise RuntimeError("empty search response")
    if UNAVAILABLE_MARKER in content:
        raise RuntimeError("provider reported no real-time search access")
    if not _has_source_urls(content):
        raise RuntimeError("provider response did not include source URLs")
    return content


async def web_search_with_fallback(query: str) -> str:
    prompt = _build_search_prompt(query)
    errors: list[str] = []

    if os.getenv("TAVILY_API_KEY"):
        try:
            content = await _run_tavily_search(query)
            logger.info("Web search succeeded with primary provider {}", PRIMARY_SEARCH_PROVIDER)
            return content
        except Exception as exc:  # noqa: BLE001
            logger.warning("Primary web search provider {} failed: {}", PRIMARY_SEARCH_PROVIDER, exc)
            errors.append(f"{PRIMARY_SEARCH_PROVIDER}: {exc}")
    else:
        errors.append(f"{PRIMARY_SEARCH_PROVIDER}: credentials unavailable")

    if os.getenv("OPENROUTER_API_KEY"):
        try:
            content = await _run_model_search(FALLBACK_PROVIDER, FALLBACK_MODEL_ID, prompt)
            logger.info(
                "Web search fallback succeeded with provider {} and model {}",
                FALLBACK_PROVIDER,
                FALLBACK_MODEL_ID,
            )
            return content
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fallback web search provider {} failed: {}", FALLBACK_PROVIDER, exc)
            errors.append(f"{FALLBACK_PROVIDER}: {exc}")
    else:
        errors.append(f"{FALLBACK_PROVIDER}: credentials unavailable")

    if os.getenv("OPENAI_COMPATIBLE_API_KEY") and os.getenv("OPENAI_COMPATIBLE_BASE_URL"):
        try:
            content = await _run_model_search(OPENAI_COMPATIBLE_PROVIDER, None, prompt)
            logger.info("Web search final fallback succeeded with provider {}", OPENAI_COMPATIBLE_PROVIDER)
            return content
        except Exception as exc:  # noqa: BLE001
            logger.warning("Final web search provider {} failed: {}", OPENAI_COMPATIBLE_PROVIDER, exc)
            errors.append(f"{OPENAI_COMPATIBLE_PROVIDER}: {exc}")
    else:
        errors.append(f"{OPENAI_COMPATIBLE_PROVIDER}: credentials unavailable")

    joined_errors = "; ".join(errors)
    raise RuntimeError(f"Web search failed. {joined_errors}")
