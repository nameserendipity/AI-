"""Scheduled A-share market-memory analysis service."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal

from agno.agent import Agent as AgnoAgent
from loguru import logger
from pydantic import BaseModel, Field

from valuecell.adapters.astock.symbols import AStockSymbolError, normalize_symbol
from valuecell.server.db.repositories.astock_memory_repository import (
    AStockMemoryRepository,
    get_astock_memory_repository,
)
from valuecell.server.db.repositories.watchlist_repository import (
    get_watchlist_repository,
)
from valuecell.utils import env as env_utils
from valuecell.utils import model as model_utils

from .strategy_preview import (
    AStockStrategyPreviewRequest,
    AStockStrategyPreviewResponse,
    AStockStrategyPreviewService,
)

MarketType = Literal["astock", "us_stock", "hk_stock", "index", "unknown"]
DEFAULT_MEMORY_USER_ID = "default_user"


class AStockMemoryLLMItem(BaseModel):
    symbol: str
    trend: Literal["bullish", "bearish", "neutral", "watch"] = "watch"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    horizon: str = "1-2 weeks"
    reason: str = ""
    risk_flags: list[str] = Field(default_factory=list)
    memory_delta: Literal[
        "continued", "strengthened", "weakened", "reversed", "new"
    ] = "new"


class AStockMemoryLLMResponse(BaseModel):
    market_summary: str = ""
    overall_risk_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    items: list[AStockMemoryLLMItem] = Field(default_factory=list)


class MemoryRunnerConfig(BaseModel):
    interval_minutes: int = Field(default=60, gt=0)
    history_limit: int = Field(default=5, ge=0)
    watchlist_user: str = DEFAULT_MEMORY_USER_ID
    market: str = "astock"
    initial_capital: float = Field(default=100000.0, gt=0)
    max_position_pct: float = Field(default=0.30, gt=0, le=1)
    open_position_pct: float = Field(default=0.10, gt=0, le=1)
    min_open_confidence: float = Field(default=0.60, ge=0, le=1)
    model_provider: str = "openai-compatible"
    model_id: str | None = None


class ClassifiedTicker(BaseModel):
    ticker: str
    market_type: MarketType
    normalized_symbol: str | None = None
    display_name: str | None = None
    skip_reason: str | None = None


class AStockMemoryService:
    """Run one A-share memory-analysis cycle and persist the result."""

    def __init__(
        self,
        *,
        config: MemoryRunnerConfig,
        repository: AStockMemoryRepository | None = None,
        preview_service: AStockStrategyPreviewService | None = None,
    ) -> None:
        self.config = config
        self.repository = repository or get_astock_memory_repository()
        self.preview_service = preview_service or AStockStrategyPreviewService()

    async def run_once(self) -> str:
        """Run one analysis cycle and return the run id."""

        started_at = datetime.now(timezone.utc)
        run_id = started_at.strftime("%Y%m%dT%H%M%S%fZ")
        self.repository.create_run(
            run_id=run_id,
            market_type=self.config.market,
            analyzer_type="astock_analysis",
            status="running",
            started_at=started_at,
            interval_minutes=self.config.interval_minutes,
            history_limit=self.config.history_limit,
            model_provider=self.config.model_provider,
            model_id=self.config.model_id,
            metadata={"watchlist_user": self.config.watchlist_user},
        )

        analyzed_items: list[tuple[ClassifiedTicker, AStockStrategyPreviewResponse]] = []
        skipped = 0
        errors = 0
        llm_result: AStockMemoryLLMResponse | None = None
        llm_raw: str | None = None
        run_error: str | None = None

        tickers = self._load_watchlist_tickers()
        try:
            for classified in [self._classify_ticker(ticker) for ticker in tickers]:
                if classified.market_type != "astock":
                    skipped += 1
                    self._persist_skipped_item(run_id, classified)
                    continue

                try:
                    preview = await self.preview_service.preview(
                        AStockStrategyPreviewRequest(
                            symbol=classified.normalized_symbol or classified.ticker,
                            initial_capital=self.config.initial_capital,
                            max_position_pct=self.config.max_position_pct,
                            open_position_pct=self.config.open_position_pct,
                            min_open_confidence=self.config.min_open_confidence,
                        )
                    )
                    analyzed_items.append((classified, preview))
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    logger.warning(
                        "A-share memory analysis failed for {}: {}",
                        classified.ticker,
                        exc,
                    )
                    self._persist_error_item(run_id, classified, str(exc))

            if analyzed_items:
                try:
                    llm_result, llm_raw = await self._call_llm(analyzed_items)
                except Exception as exc:  # noqa: BLE001
                    run_error = f"LLM analysis failed: {exc}"
                    logger.warning(run_error)
                    llm_result = self._fallback_memory_response(
                        analyzed_items, reason=run_error
                    )
                    llm_raw = llm_result.model_dump_json()

            llm_items = {
                item.symbol.upper(): item for item in (llm_result.items if llm_result else [])
            }
            for classified, preview in analyzed_items:
                self._persist_analyzed_item(run_id, classified, preview, llm_items)

            status = "completed" if run_error is None else "partial"
            self.repository.finalize_run(
                run_id=run_id,
                status=status,
                completed_at=datetime.now(timezone.utc),
                total_items=len(tickers),
                analyzed_items=len(analyzed_items),
                skipped_items=skipped,
                error_items=errors,
                market_summary=llm_result.market_summary if llm_result else None,
                overall_risk_level=(
                    llm_result.overall_risk_level if llm_result else None
                ),
                llm_raw=llm_raw,
                error_message=run_error,
                metadata={
                    "watchlist_user": self.config.watchlist_user,
                    "market": self.config.market,
                },
            )
            logger.info(
                "A-share memory run {} finished: analyzed={}, skipped={}, errors={}",
                run_id,
                len(analyzed_items),
                skipped,
                errors,
            )
            return run_id
        except Exception as exc:
            self.repository.finalize_run(
                run_id=run_id,
                status="error",
                completed_at=datetime.now(timezone.utc),
                total_items=len(tickers),
                analyzed_items=len(analyzed_items),
                skipped_items=skipped,
                error_items=errors,
                error_message=str(exc),
            )
            raise

    def _load_watchlist_tickers(self) -> list[str]:
        watchlist = get_watchlist_repository().get_default_watchlist(
            self.config.watchlist_user
        )
        if not watchlist:
            return []
        return [item.ticker for item in watchlist.items]

    def _classify_ticker(self, ticker: str) -> ClassifiedTicker:
        try:
            normalized = normalize_symbol(ticker)
            return ClassifiedTicker(
                ticker=ticker,
                market_type="astock",
                normalized_symbol=normalized.canonical,
                display_name=normalized.internal_ticker,
            )
        except AStockSymbolError:
            pass

        prefix = ticker.split(":", 1)[0].upper() if ":" in ticker else ""
        if prefix in {"NASDAQ", "NYSE", "AMEX"}:
            return ClassifiedTicker(
                ticker=ticker,
                market_type="us_stock",
                normalized_symbol=ticker,
                skip_reason="US stock is recognized but not supported by this runner yet.",
            )
        if prefix == "HKEX":
            return ClassifiedTicker(
                ticker=ticker,
                market_type="hk_stock",
                normalized_symbol=ticker,
                skip_reason="HK stock is recognized but not supported by this runner yet.",
            )
        if prefix in {"INDEX", "CRYPTO", "YFINANCE"}:
            return ClassifiedTicker(
                ticker=ticker,
                market_type="index",
                normalized_symbol=ticker,
                skip_reason=f"{prefix} assets are not supported by this runner yet.",
            )
        return ClassifiedTicker(
            ticker=ticker,
            market_type="unknown",
            normalized_symbol=ticker,
            skip_reason="Ticker market could not be classified.",
        )

    async def _call_llm(
        self,
        analyzed_items: list[tuple[ClassifiedTicker, AStockStrategyPreviewResponse]],
    ) -> tuple[AStockMemoryLLMResponse, str]:
        model = model_utils.create_model_with_provider(
            provider=self.config.model_provider,
            model_id=self.config.model_id,
        )
        agent = AgnoAgent(
            model=model,
            output_schema=AStockMemoryLLMResponse,
            markdown=False,
            use_json_mode=model_utils.model_should_use_json_mode(model),
            debug_mode=env_utils.agent_debug_mode_enabled(),
            instructions=[self._system_prompt()],
        )
        prompt = self._build_llm_prompt(analyzed_items)
        response = await agent.arun(prompt)
        content = getattr(response, "content", None) or response
        if isinstance(content, AStockMemoryLLMResponse):
            return content, content.model_dump_json()
        if isinstance(content, dict):
            parsed = AStockMemoryLLMResponse.model_validate(content)
            return parsed, json.dumps(content, ensure_ascii=False)
        if isinstance(content, str):
            parsed = AStockMemoryLLMResponse.model_validate_json(content)
            return parsed, content
        raise ValueError(f"Unexpected LLM response type: {type(content)!r}")

    def _build_llm_prompt(
        self,
        analyzed_items: list[tuple[ClassifiedTicker, AStockStrategyPreviewResponse]],
    ) -> str:
        current_items = []
        history_by_symbol = {}
        for classified, preview in analyzed_items:
            report = preview.analysis
            symbol = report.symbol.upper()
            current_items.append(
                {
                    "symbol": report.symbol,
                    "name": report.name,
                    "action": preview.action,
                    "score_inputs": {
                        "bias": report.bias,
                        "confidence": report.confidence,
                        "latest_price": report.technical.latest_close,
                        "change_5d_pct": report.technical.change_5d_pct,
                        "change_20d_pct": report.technical.change_20d_pct,
                    },
                    "summary": report.summary,
                    "key_points": report.key_points,
                    "risk_flags": report.risk_flags,
                    "blocked_reasons": preview.blocked_reasons,
                }
            )
            history_items = self.repository.recent_items_by_symbol(
                normalized_symbol=report.symbol,
                market_type="astock",
                limit=self.config.history_limit,
            )
            history_by_symbol[symbol] = [
                {
                    "created_at": item.created_at.isoformat()
                    if item.created_at
                    else None,
                    "trend": item.trend,
                    "confidence": item.confidence,
                    "reason": item.reason,
                    "memory_delta": item.memory_delta,
                    "bias": item.bias,
                    "action": item.action,
                }
                for item in history_items
            ]

        payload = {
            "task": "Judge 1-2 week A-share swing trend and update market memory.",
            "disclaimer": (
                "This is non-advisory market research for memory tracking only, "
                "not investment advice or an instruction to trade."
            ),
            "horizon": "1-2 weeks",
            "current_analysis": current_items,
            "recent_memory_by_symbol": history_by_symbol,
            "output_contract": {
                "trend": "bullish | bearish | neutral | watch",
                "memory_delta": "continued | strengthened | weakened | reversed | new",
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _system_prompt(self) -> str:
        return (
            "You are an A-share market research memory analyst. "
            "Use current structured analysis and recent memory to produce a "
            "non-advisory 1-2 week research outlook. Do not suggest live trading, "
            "do not guarantee outcomes, and do not tell the user to buy or sell. "
            "Be concise, risk-aware, and return only the requested JSON schema."
        )

    def _fallback_memory_response(
        self,
        analyzed_items: list[tuple[ClassifiedTicker, AStockStrategyPreviewResponse]],
        *,
        reason: str,
    ) -> AStockMemoryLLMResponse:
        """Build deterministic memory if the LLM is unavailable or blocked."""
        items: list[AStockMemoryLLMItem] = []
        bearish_count = 0
        bullish_count = 0
        for _, preview in analyzed_items:
            report = preview.analysis
            trend = self._trend_from_bias(report.bias)
            if trend == "bearish":
                bearish_count += 1
            elif trend == "bullish":
                bullish_count += 1
            items.append(
                AStockMemoryLLMItem(
                    symbol=report.symbol,
                    trend=trend,
                    confidence=float(report.confidence or 0.0),
                    horizon="1-2 weeks",
                    reason=(
                        f"Rule fallback because LLM was unavailable. {report.summary}"
                    ),
                    risk_flags=list(report.risk_flags or []),
                    memory_delta=self._fallback_memory_delta(report.symbol, trend),
                )
            )
        risk = "medium"
        if bearish_count > bullish_count and bearish_count >= max(1, len(items) // 2):
            risk = "high"
        elif bullish_count > bearish_count:
            risk = "medium"
        return AStockMemoryLLMResponse(
            market_summary=(
                "LLM synthesis was unavailable; stored deterministic A-share "
                f"analysis fallback. Cause: {reason}"
            ),
            overall_risk_level=risk,
            items=items,
        )

    def _trend_from_bias(self, bias: str | None) -> str:
        if bias == "bullish":
            return "bullish"
        if bias == "bearish":
            return "bearish"
        if bias == "neutral":
            return "neutral"
        return "watch"

    def _fallback_memory_delta(self, symbol: str, trend: str) -> str:
        recent = self.repository.recent_items_by_symbol(
            normalized_symbol=symbol,
            market_type="astock",
            limit=1,
        )
        if not recent or not recent[0].trend:
            return "new"
        previous = recent[0].trend
        if previous == trend:
            return "continued"
        return "reversed"

    def _persist_skipped_item(
        self,
        run_id: str,
        classified: ClassifiedTicker,
    ) -> None:
        self.repository.add_item(
            run_id=run_id,
            ticker=classified.ticker,
            normalized_symbol=classified.normalized_symbol,
            display_name=classified.display_name,
            market_type=classified.market_type,
            analyzer_type="unsupported",
            data_source=None,
            status="unsupported_in_runner",
            skip_reason=classified.skip_reason,
        )

    def _persist_error_item(
        self,
        run_id: str,
        classified: ClassifiedTicker,
        error: str,
    ) -> None:
        self.repository.add_item(
            run_id=run_id,
            ticker=classified.ticker,
            normalized_symbol=classified.normalized_symbol,
            display_name=classified.display_name,
            market_type=classified.market_type,
            analyzer_type="astock_analysis",
            data_source="astock_analysis_service",
            status="error",
            error_message=error,
        )

    def _persist_analyzed_item(
        self,
        run_id: str,
        classified: ClassifiedTicker,
        preview: AStockStrategyPreviewResponse,
        llm_items: dict[str, AStockMemoryLLMItem],
    ) -> None:
        report = preview.analysis
        llm_item = llm_items.get(report.symbol.upper())
        self.repository.add_item(
            run_id=run_id,
            ticker=classified.ticker,
            normalized_symbol=report.symbol,
            display_name=report.name or classified.display_name,
            market_type="astock",
            analyzer_type="astock_analysis",
            data_source="astock_analysis_service",
            status="analyzed" if llm_item else "analyzed_without_llm",
            trend=llm_item.trend if llm_item else None,
            confidence=llm_item.confidence if llm_item else None,
            horizon=llm_item.horizon if llm_item else "1-2 weeks",
            reason=llm_item.reason if llm_item else None,
            memory_delta=llm_item.memory_delta if llm_item else None,
            action=preview.action,
            bias=report.bias,
            latest_price=report.technical.latest_close,
            change_5d_pct=report.technical.change_5d_pct,
            change_20d_pct=report.technical.change_20d_pct,
            risk_flags=report.risk_flags,
            key_points=report.key_points,
            blocked_reasons=preview.blocked_reasons,
            analysis_snapshot=preview.model_dump(mode="json"),
            llm_item=llm_item.model_dump(mode="json") if llm_item else None,
        )
