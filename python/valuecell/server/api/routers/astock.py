"""A-share data API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from valuecell.adapters.astock.schemas import (
    Announcement,
    AStockSnapshot,
    CompanyProfile,
    FinancialSummary,
    Kline,
    NewsItem,
    Quote,
)
from valuecell.adapters.astock.symbols import AStockSymbolError
from valuecell.server.services.astock import (
    AStockAnalysisReport,
    AStockAnalysisService,
    get_astock_data_service,
)

from .watchlist import DEFAULT_USER_ID
from ..schemas import SuccessResponse


def create_astock_router() -> APIRouter:
    """Create A-share data routes."""
    router = APIRouter(prefix="/astock", tags=["AStock"])
    service = get_astock_data_service()
    analysis_service = AStockAnalysisService(data_service=service)

    @router.get(
        "/watchlist/scan",
        summary="Batch scan default watchlist A-shares",
    )
    async def scan_default_watchlist(
        initial_capital: float = Query(100000.0, gt=0),
        max_position_pct: float = Query(0.30, gt=0, le=1),
        open_position_pct: float = Query(0.10, gt=0, le=1),
        min_open_confidence: float = Query(0.60, ge=0, le=1),
        persist: bool = Query(True),
    ):
        from valuecell.server.db.repositories.watchlist_repository import (
            get_watchlist_repository,
        )
        from valuecell.server.services.astock.strategy_preview import (
            AStockStrategyPreviewService,
        )
        from valuecell.server.services.astock.watchlist_scan import (
            AStockWatchlistScanRequest,
            AStockWatchlistScanService,
        )

        watchlist = get_watchlist_repository().get_default_watchlist(DEFAULT_USER_ID)
        tickers = [item.ticker for item in watchlist.items] if watchlist else []
        preview_service = AStockStrategyPreviewService()
        scan_service = AStockWatchlistScanService(preview_service=preview_service)
        result = await scan_service.scan(
            AStockWatchlistScanRequest(
                tickers=tickers,
                initial_capital=initial_capital,
                max_position_pct=max_position_pct,
                open_position_pct=open_position_pct,
                min_open_confidence=min_open_confidence,
                persist=persist,
            )
        )
        return SuccessResponse.create(data=result)

    @router.get(
        "/watchlist/summary",
        summary="Summarize latest A-share watchlist scan",
    )
    async def summarize_watchlist_scan(use_llm: bool = Query(False)):
        from valuecell.server.services.astock.watchlist_scan import (
            AStockWatchlistScanService,
        )

        scan_service = AStockWatchlistScanService()
        result = scan_service.summarize_latest(use_llm=use_llm)
        return SuccessResponse.create(data=result)

    @router.get(
        "/memory/latest",
        summary="Get latest scheduled DeepSeek A-share memory analysis",
    )
    async def get_latest_memory(
        include_skipped: bool = Query(True),
        limit: int = Query(100, ge=1, le=500),
    ):
        from valuecell.server.db.repositories.astock_memory_repository import (
            get_astock_memory_repository,
        )

        repo = get_astock_memory_repository()
        run = repo.latest_run(market_type="astock")
        if run is None:
            return SuccessResponse.create(data={"run": None, "items": []})

        items = repo.items_for_run(
            run_id=run.run_id,
            include_skipped=include_skipped,
            limit=limit,
        )

        def _dt(value):
            return value.isoformat() if value else None

        return SuccessResponse.create(
            data={
                "run": {
                    "run_id": run.run_id,
                    "market_type": run.market_type,
                    "analyzer_type": run.analyzer_type,
                    "status": run.status,
                    "started_at": _dt(run.started_at),
                    "completed_at": _dt(run.completed_at),
                    "interval_minutes": run.interval_minutes,
                    "history_limit": run.history_limit,
                    "total_items": run.total_items,
                    "analyzed_items": run.analyzed_items,
                    "skipped_items": run.skipped_items,
                    "error_items": run.error_items,
                    "model_provider": run.model_provider,
                    "model_id": run.model_id,
                    "market_summary": run.market_summary,
                    "overall_risk_level": run.overall_risk_level,
                    "error_message": run.error_message,
                    "metadata": run.run_metadata or {},
                },
                "items": [
                    {
                        "id": item.id,
                        "run_id": item.run_id,
                        "ticker": item.ticker,
                        "normalized_symbol": item.normalized_symbol,
                        "display_name": item.display_name,
                        "market_type": item.market_type,
                        "analyzer_type": item.analyzer_type,
                        "data_source": item.data_source,
                        "status": item.status,
                        "skip_reason": item.skip_reason,
                        "error_message": item.error_message,
                        "trend": item.trend,
                        "confidence": item.confidence,
                        "horizon": item.horizon,
                        "reason": item.reason,
                        "memory_delta": item.memory_delta,
                        "score": item.score,
                        "action": item.action,
                        "bias": item.bias,
                        "latest_price": item.latest_price,
                        "change_5d_pct": item.change_5d_pct,
                        "change_20d_pct": item.change_20d_pct,
                        "risk_flags": item.risk_flags or [],
                        "key_points": item.key_points or [],
                        "blocked_reasons": item.blocked_reasons or [],
                        "analysis_snapshot": item.analysis_snapshot or {},
                        "llm_item": item.llm_item or {},
                        "created_at": _dt(item.created_at),
                        "updated_at": _dt(item.updated_at),
                    }
                    for item in items
                ],
            }
        )
    @router.get(
        "/{symbol}/snapshot",
        response_model=SuccessResponse[AStockSnapshot],
        summary="Get A-share full snapshot",
    )
    async def get_snapshot(
        symbol: str,
        kline_period: str = Query("daily", description="Kline period"),
        kline_limit: int = Query(120, ge=1, le=1000),
        news_limit: int = Query(10, ge=0, le=50),
        announcement_limit: int = Query(10, ge=0, le=50),
    ):
        try:
            snapshot = await service.get_full_snapshot(
                symbol,
                kline_period=kline_period,
                kline_limit=kline_limit,
                news_limit=news_limit,
                announcement_limit=announcement_limit,
            )
            return SuccessResponse.create(data=snapshot)
        except AStockSymbolError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get(
        "/{symbol}/analysis",
        response_model=SuccessResponse[AStockAnalysisReport],
        summary="Analyze A-share stock",
    )
    async def analyze_symbol(
        symbol: str,
        kline_limit: int = Query(120, ge=20, le=1000),
        news_limit: int = Query(10, ge=0, le=50),
        announcement_limit: int = Query(10, ge=0, le=50),
    ):
        try:
            report = await analysis_service.analyze_symbol(
                symbol,
                kline_limit=kline_limit,
                news_limit=news_limit,
                announcement_limit=announcement_limit,
            )
            return SuccessResponse.create(data=report)
        except AStockSymbolError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get(
        "/{symbol}/strategy-preview",
        summary="Preview A-share strategy decision without placing orders",
    )
    async def preview_strategy(
        symbol: str,
        initial_capital: float = Query(100000.0, gt=0),
        current_position_qty: float = Query(0.0, ge=0),
        max_position_pct: float = Query(0.30, gt=0, le=1),
        open_position_pct: float = Query(0.10, gt=0, le=1),
        min_open_confidence: float = Query(0.60, ge=0, le=1),
    ):
        try:
            from valuecell.server.services.astock.strategy_preview import (
                AStockStrategyPreviewRequest,
                AStockStrategyPreviewService,
            )

            preview_service = AStockStrategyPreviewService()
            result = await preview_service.preview(
                AStockStrategyPreviewRequest(
                    symbol=symbol,
                    initial_capital=initial_capital,
                    current_position_qty=current_position_qty,
                    max_position_pct=max_position_pct,
                    open_position_pct=open_position_pct,
                    min_open_confidence=min_open_confidence,
                )
            )
            return SuccessResponse.create(data=result)
        except AStockSymbolError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get(
        "/{symbol}/quote",
        response_model=SuccessResponse[Quote | None],
        summary="Get A-share quote",
    )
    async def get_quote(symbol: str):
        try:
            return SuccessResponse.create(data=await service.get_quote(symbol))
        except AStockSymbolError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get(
        "/{symbol}/klines",
        response_model=SuccessResponse[list[Kline]],
        summary="Get A-share klines",
    )
    async def get_klines(
        symbol: str,
        period: str = Query("daily"),
        limit: int = Query(250, ge=1, le=2000),
    ):
        try:
            data = await service.get_kline(symbol, period=period, limit=limit)
            return SuccessResponse.create(data=data)
        except AStockSymbolError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get(
        "/{symbol}/profile",
        response_model=SuccessResponse[CompanyProfile | None],
        summary="Get A-share company profile",
    )
    async def get_profile(symbol: str):
        try:
            return SuccessResponse.create(data=await service.get_company_profile(symbol))
        except AStockSymbolError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get(
        "/{symbol}/financials",
        response_model=SuccessResponse[FinancialSummary | None],
        summary="Get A-share financial summary",
    )
    async def get_financials(symbol: str):
        try:
            return SuccessResponse.create(data=await service.get_financials(symbol))
        except AStockSymbolError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get(
        "/{symbol}/announcements",
        response_model=SuccessResponse[list[Announcement]],
        summary="Get A-share announcements",
    )
    async def get_announcements(
        symbol: str,
        limit: int = Query(20, ge=1, le=100),
    ):
        try:
            return SuccessResponse.create(
                data=await service.get_announcements(symbol, limit=limit)
            )
        except AStockSymbolError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get(
        "/{symbol}/news",
        response_model=SuccessResponse[list[NewsItem]],
        summary="Get A-share news",
    )
    async def get_news(symbol: str, limit: int = Query(20, ge=1, le=100)):
        try:
            return SuccessResponse.create(data=await service.get_news(symbol, limit=limit))
        except AStockSymbolError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router


