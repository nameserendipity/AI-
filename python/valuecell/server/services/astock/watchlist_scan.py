"""Batch scan A-share watchlists and persist compact research memory."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from loguru import logger
from pydantic import BaseModel, Field

from valuecell.adapters.astock.symbols import AStockSymbolError, normalize_symbol
from valuecell.utils.env import get_system_env_dir

from .strategy_preview import (
    AStockStrategyPreviewRequest,
    AStockStrategyPreviewResponse,
    AStockStrategyPreviewService,
)

ScanBucket = Literal["candidate", "watch", "risk", "exit", "skipped", "error"]


class AStockWatchlistScanRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    initial_capital: float = Field(default=100000.0, gt=0)
    current_positions: dict[str, float] = Field(default_factory=dict)
    max_position_pct: float = Field(default=0.30, gt=0, le=1)
    open_position_pct: float = Field(default=0.10, gt=0, le=1)
    min_open_confidence: float = Field(default=0.60, ge=0, le=1)
    persist: bool = True


class AStockWatchlistScanItem(BaseModel):
    ticker: str
    symbol: str | None = None
    display_name: str | None = None
    bucket: ScanBucket
    score: float = 0.0
    action: str = "hold"
    bias: str = "unknown"
    confidence: float = 0.0
    latest_price: float | None = None
    change_5d_pct: float | None = None
    change_20d_pct: float | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    summary: str = ""
    error: str | None = None
    preview: AStockStrategyPreviewResponse | None = None


class AStockWatchlistScanResponse(BaseModel):
    run_id: str
    generated_at: str
    total: int
    scanned: int
    skipped: int
    persisted_path: str | None = None
    items: list[AStockWatchlistScanItem]


class AStockWatchlistSummaryResponse(BaseModel):
    run_id: str | None = None
    generated_at: str | None = None
    total: int = 0
    scanned: int = 0
    candidate_count: int = 0
    watch_count: int = 0
    risk_count: int = 0
    exit_count: int = 0
    skipped_count: int = 0
    top_candidates: list[AStockWatchlistScanItem] = Field(default_factory=list)
    risk_items: list[AStockWatchlistScanItem] = Field(default_factory=list)
    report_lines: list[str] = Field(default_factory=list)
    compact_context: str = ""
    source_path: str | None = None
    llm_summary: str | None = None


def get_astock_memory_dir() -> Path:
    path = Path(get_system_env_dir()) / "astock" / "analysis_runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_astock_watchlist_ticker(ticker: str) -> bool:
    try:
        normalize_symbol(ticker)
    except AStockSymbolError:
        return False
    return True


class AStockWatchlistScanService:
    """Scan a list of A-share tickers with the dry-run strategy preview."""

    def __init__(self, preview_service: AStockStrategyPreviewService | None = None) -> None:
        self.preview_service = preview_service or AStockStrategyPreviewService()

    async def scan(
        self, request: AStockWatchlistScanRequest
    ) -> AStockWatchlistScanResponse:
        generated_at = datetime.utcnow().isoformat()
        run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        items: list[AStockWatchlistScanItem] = []

        for ticker in request.tickers:
            normalized = self._normalize_ticker(ticker)
            if normalized is None:
                items.append(
                    AStockWatchlistScanItem(
                        ticker=ticker,
                        bucket="skipped",
                        summary="非 A股标的，批量预检已跳过。",
                    )
                )
                continue

            try:
                preview = await self.preview_service.preview(
                    AStockStrategyPreviewRequest(
                        symbol=normalized.canonical,
                        initial_capital=request.initial_capital,
                        current_position_qty=request.current_positions.get(
                            normalized.internal_ticker,
                            request.current_positions.get(normalized.code, 0.0),
                        ),
                        max_position_pct=request.max_position_pct,
                        open_position_pct=request.open_position_pct,
                        min_open_confidence=request.min_open_confidence,
                    )
                )
                items.append(self._item_from_preview(normalized.internal_ticker, preview))
            except Exception as exc:  # noqa: BLE001
                logger.warning("A-share watchlist scan failed for {}: {}", ticker, exc)
                items.append(
                    AStockWatchlistScanItem(
                        ticker=normalized.internal_ticker,
                        symbol=normalized.canonical,
                        bucket="error",
                        summary="扫描失败。",
                        error=str(exc),
                    )
                )

        items.sort(key=lambda item: item.score, reverse=True)
        response = AStockWatchlistScanResponse(
            run_id=run_id,
            generated_at=generated_at,
            total=len(request.tickers),
            scanned=len([item for item in items if item.bucket not in {"skipped", "error"}]),
            skipped=len([item for item in items if item.bucket in {"skipped", "error"}]),
            items=items,
        )
        if request.persist:
            response.persisted_path = str(self._persist(response))
        return response

    def _normalize_ticker(self, ticker: str):
        try:
            return normalize_symbol(ticker)
        except AStockSymbolError:
            return None

    def _item_from_preview(
        self,
        ticker: str,
        preview: AStockStrategyPreviewResponse,
    ) -> AStockWatchlistScanItem:
        report = preview.analysis
        score = self._score(preview)
        return AStockWatchlistScanItem(
            ticker=ticker,
            symbol=report.symbol,
            display_name=report.name or report.code,
            bucket=self._bucket(preview, score),
            score=score,
            action=preview.action,
            bias=report.bias,
            confidence=report.confidence,
            latest_price=report.technical.latest_close,
            change_5d_pct=report.technical.change_5d_pct,
            change_20d_pct=report.technical.change_20d_pct,
            blocked_reasons=preview.blocked_reasons,
            key_points=report.key_points,
            risk_flags=report.risk_flags,
            summary=report.summary,
            preview=preview,
        )

    def _score(self, preview: AStockStrategyPreviewResponse) -> float:
        report = preview.analysis
        bias_score = {
            "bullish": 35.0,
            "neutral": 12.0,
            "mixed": 6.0,
            "unknown": 0.0,
            "bearish": -20.0,
        }.get(report.bias, 0.0)
        action_score = {"buy": 25.0, "hold": 0.0, "sell": -25.0}.get(
            preview.action, 0.0
        )
        risk_penalty = 8.0 * len(report.risk_flags)
        blocked_penalty = 4.0 * len(preview.blocked_reasons)
        return round(
            bias_score
            + action_score
            + report.confidence * 40.0
            - risk_penalty
            - blocked_penalty,
            2,
        )

    def _bucket(
        self,
        preview: AStockStrategyPreviewResponse,
        score: float,
    ) -> ScanBucket:
        report = preview.analysis
        if preview.action == "sell":
            return "exit"
        if report.risk_flags:
            return "risk"
        if preview.action == "buy" or (
            report.bias == "bullish" and report.confidence >= 0.60 and score >= 45
        ):
            return "candidate"
        return "watch"

    def _persist(self, response: AStockWatchlistScanResponse) -> Path:
        directory = get_astock_memory_dir()
        path = directory / f"{response.run_id}.json"
        path.write_text(
            json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        latest_path = directory / "latest.json"
        latest_path.write_text(
            json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path


    def summarize_latest(self, *, use_llm: bool = False) -> AStockWatchlistSummaryResponse:
        """Summarize the latest persisted scan without fetching market data again."""
        latest_path = get_astock_memory_dir() / "latest.json"
        if not latest_path.exists():
            return AStockWatchlistSummaryResponse(
                report_lines=["No scan record yet. Run watchlist scan first."],
                compact_context="No persisted A-share watchlist scan is available.",
            )

        payload = json.loads(latest_path.read_text(encoding="utf-8"))
        scan = AStockWatchlistScanResponse.model_validate(payload)
        groups = self._group_items(scan.items)
        top_candidates = sorted(
            [*groups["candidate"], *groups["watch"]],
            key=lambda item: item.score,
            reverse=True,
        )[:5]
        risk_items = [*groups["risk"], *groups["exit"], *groups["error"]]
        lines = self._build_report_lines(scan, groups, top_candidates, risk_items)
        compact_context = self._build_compact_context(scan, top_candidates, risk_items)
        return AStockWatchlistSummaryResponse(
            run_id=scan.run_id,
            generated_at=scan.generated_at,
            total=scan.total,
            scanned=scan.scanned,
            candidate_count=len(groups["candidate"]),
            watch_count=len(groups["watch"]),
            risk_count=len(groups["risk"]),
            exit_count=len(groups["exit"]),
            skipped_count=len(groups["skipped"]) + len(groups["error"]),
            top_candidates=top_candidates,
            risk_items=risk_items[:5],
            report_lines=lines,
            compact_context=compact_context,
            source_path=str(latest_path),
            llm_summary=None if not use_llm else "LLM summary is not enabled yet.",
        )

    def _group_items(
        self, items: list[AStockWatchlistScanItem]
    ) -> dict[ScanBucket, list[AStockWatchlistScanItem]]:
        groups: dict[ScanBucket, list[AStockWatchlistScanItem]] = {
            "candidate": [],
            "watch": [],
            "risk": [],
            "exit": [],
            "skipped": [],
            "error": [],
        }
        for item in items:
            groups[item.bucket].append(item)
        return groups

    def _build_report_lines(
        self,
        scan: AStockWatchlistScanResponse,
        groups: dict[ScanBucket, list[AStockWatchlistScanItem]],
        top_candidates: list[AStockWatchlistScanItem],
        risk_items: list[AStockWatchlistScanItem],
    ) -> list[str]:
        lines = [
            f"Scanned {scan.total} watchlist items, including {scan.scanned} valid A-share items.",
            (
                f"Candidates {len(groups['candidate'])}, watch {len(groups['watch'])}, "
                f"risk {len(groups['risk'])}, exit {len(groups['exit'])}."
            ),
        ]
        if top_candidates:
            top = top_candidates[0]
            lines.append(
                f"Top ranked item is {top.display_name or top.ticker}: "
                f"score {top.score:.0f}, bias {top.bias}, confidence {top.confidence:.0%}."
            )
        if risk_items:
            names = ", ".join((item.display_name or item.ticker) for item in risk_items[:3])
            lines.append(f"Review risk items first: {names}.")
        if not groups["candidate"]:
            lines.append("No strong candidate was triggered. Continue observing or wait for clearer signals.")
        return lines

    def _build_compact_context(
        self,
        scan: AStockWatchlistScanResponse,
        top_candidates: list[AStockWatchlistScanItem],
        risk_items: list[AStockWatchlistScanItem],
    ) -> str:
        chunks = [
            f"run_id={scan.run_id}; generated_at={scan.generated_at}; "
            f"total={scan.total}; scanned={scan.scanned}",
            "Top candidates:",
        ]
        for item in top_candidates:
            chunks.append(
                f"- {item.symbol or item.ticker}: bucket={item.bucket}, score={item.score}, "
                f"bias={item.bias}, confidence={item.confidence}, action={item.action}, "
                f"summary={item.summary}"
            )
        chunks.append("Risk items:")
        for item in risk_items:
            chunks.append(
                f"- {item.symbol or item.ticker}: bucket={item.bucket}, "
                f"risk_flags={item.risk_flags}, blocked={item.blocked_reasons}"
            )
        return "\n".join(chunks)
