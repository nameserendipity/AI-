"""Tavily fallback news adapter for A-share symbols."""

from __future__ import annotations

import os
from typing import Any

import aiohttp
from loguru import logger

from .schemas import NewsItem
from .symbols import normalize_symbol

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilyAStockNewsAdapter:
    """Fetch stock-related news with Tavily when structured news APIs fail."""

    source = "tavily"

    async def get_news(self, symbol: str, *, limit: int = 10, name: str | None = None) -> list[NewsItem]:
        api_key = os.getenv("TAVILY_API_KEY", "").strip()
        if not api_key:
            return []
        stock = normalize_symbol(symbol)
        query_name = f" {name}" if name else ""
        query = f"{stock.code}{query_name} A股 最新 新闻 公告 财经"
        payload: dict[str, Any] = {
            "query": query,
            "search_depth": os.getenv("TAVILY_SEARCH_DEPTH", "basic"),
            "topic": "news",
            "max_results": max(1, min(limit, 10)),
            "include_answer": False,
            "include_raw_content": False,
        }
        try:
            data = await self._post(payload, api_key, use_bearer=True)
        except Exception as bearer_exc:  # noqa: BLE001
            logger.debug("Tavily bearer auth failed for A-stock news: {}", bearer_exc)
            try:
                data = await self._post(payload, api_key, use_bearer=False)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Tavily A-stock news failed for {}: {}", stock.canonical, exc)
                return []

        results = data.get("results") or []
        records: list[NewsItem] = []
        for item in results[:limit]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            if not title:
                continue
            records.append(
                NewsItem(
                    symbol=stock.canonical,
                    code=stock.code,
                    exchange=stock.exchange,
                    source=self.source,
                    title=title,
                    publish_time=str(
                        item.get("published_date") or item.get("publishedDate") or ""
                    )
                    or None,
                    url=url or None,
                    summary=str(item.get("content") or "") or None,
                    raw=item,
                )
            )
        return records

    async def _post(self, payload: dict[str, Any], api_key: str, *, use_bearer: bool) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        body = dict(payload)
        if use_bearer:
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            body["api_key"] = api_key
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(TAVILY_SEARCH_URL, json=body, headers=headers) as response:
                text = await response.text()
                if response.status >= 400:
                    raise RuntimeError(f"Tavily HTTP {response.status}: {text[:300]}")
                data = await response.json(content_type=None)
                if not isinstance(data, dict):
                    raise RuntimeError("invalid Tavily response")
                return data
