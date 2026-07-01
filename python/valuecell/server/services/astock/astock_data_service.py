"""High-level A-share data service.

This service is the single entry point for A-share data consumers. Agents should
call this service instead of directly depending on AkShare, mootdx, or any other
provider-specific API.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Optional

from loguru import logger

from valuecell.adapters.astock.cache import read_json_cache, write_json_cache
from valuecell.adapters.astock.schemas import (
    Announcement,
    AStockSnapshot,
    CompanyProfile,
    FinancialSummary,
    Kline,
    NewsItem,
    Quote,
    SourceStatus,
)
from valuecell.adapters.astock.symbols import normalize_symbol

if TYPE_CHECKING:
    from valuecell.adapters.astock.akshare import AkShareAStockAdapter
    from valuecell.adapters.astock.cninfo import CNInfoAStockAdapter
    from valuecell.adapters.astock.mootdx import MootdxAStockAdapter
    from valuecell.adapters.astock.tavily_news import TavilyAStockNewsAdapter


class AStockDataService:
    """Unified A-share data service.

    MVP implementation uses AkShare as the first adapter. Future adapters
    (mootdx, Tushare, Eastmoney, CNINFO) should be added behind this service
    without changing Agent-facing APIs.
    """

    def __init__(
        self,
        akshare_adapter: Optional["AkShareAStockAdapter"] = None,
        mootdx_adapter: Optional["MootdxAStockAdapter"] = None,
        cninfo_adapter: Optional["CNInfoAStockAdapter"] = None,
        tavily_news_adapter: Optional["TavilyAStockNewsAdapter"] = None,
    ) -> None:
        self._akshare = akshare_adapter
        self._mootdx = mootdx_adapter
        self._cninfo = cninfo_adapter
        self._tavily_news = tavily_news_adapter

    @property
    def akshare(self) -> "AkShareAStockAdapter":
        if self._akshare is None:
            from valuecell.adapters.astock.akshare import AkShareAStockAdapter

            self._akshare = AkShareAStockAdapter()
        return self._akshare

    @property
    def mootdx(self) -> "MootdxAStockAdapter":
        if self._mootdx is None:
            from valuecell.adapters.astock.mootdx import MootdxAStockAdapter

            self._mootdx = MootdxAStockAdapter()
        return self._mootdx

    @property
    def cninfo(self) -> "CNInfoAStockAdapter":
        if self._cninfo is None:
            from valuecell.adapters.astock.cninfo import CNInfoAStockAdapter

            self._cninfo = CNInfoAStockAdapter()
        return self._cninfo

    @property
    def tavily_news(self) -> "TavilyAStockNewsAdapter":
        if self._tavily_news is None:
            from valuecell.adapters.astock.tavily_news import TavilyAStockNewsAdapter

            self._tavily_news = TavilyAStockNewsAdapter()
        return self._tavily_news

    async def get_quote(self, symbol: str) -> Quote | None:
        quote = await self.mootdx.get_quote(symbol)
        if quote is not None:
            return quote
        return await self.akshare.get_quote(symbol)

    async def get_kline(
        self,
        symbol: str,
        *,
        period: str = "daily",
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        adjust: str = "",
        limit: int = 250,
    ) -> list[Kline]:
        # Prefer mootdx for A-share market data. Fall back to AkShare because
        # mootdx is optional and endpoint availability can vary by network.
        if start_date is None and end_date is None and not adjust:
            klines = await self.mootdx.get_kline(symbol, period=period, limit=limit)
            if klines:
                return klines

        return await self.akshare.get_kline(
            symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            limit=limit,
        )

    async def get_company_profile(self, symbol: str) -> CompanyProfile | None:
        profile = await self.mootdx.get_company_profile(symbol)
        if profile is not None:
            return profile
        return await self.akshare.get_company_profile(symbol)

    async def get_financials(self, symbol: str) -> FinancialSummary | None:
        financials = await self.mootdx.get_financials(symbol)
        if financials is not None:
            return financials
        stock = normalize_symbol(symbol)
        logger.info("Financial summary unavailable for {}", stock.canonical)
        return None

    async def get_announcements(self, symbol: str, *, limit: int = 20) -> list[Announcement]:
        announcements = await self.cninfo.get_announcements(symbol, limit=limit)
        if announcements:
            return announcements
        return await self.akshare.get_announcements(symbol, limit=limit)

    async def get_news(self, symbol: str, *, limit: int = 20) -> list[NewsItem]:
        news = await self.akshare.get_news(symbol, limit=limit)
        if news:
            return news
        return await self.tavily_news.get_news(symbol, limit=limit)

    async def get_full_snapshot(
        self,
        symbol: str,
        *,
        kline_period: str = "daily",
        kline_limit: int = 120,
        news_limit: int = 10,
        announcement_limit: int = 10,
    ) -> AStockSnapshot:
        """Fetch the first-stage A-share snapshot for analysis agents."""
        stock = normalize_symbol(symbol)
        statuses: list[SourceStatus] = []
        cached_snapshot = self._read_cached_snapshot(stock.canonical)

        quote = await self.get_quote(stock.canonical)
        statuses.append(
            SourceStatus(
                source="mootdx.quote|akshare.quote",
                ok=quote is not None,
                message=None if quote is not None else "quote unavailable",
            )
        )

        klines = await self.get_kline(
            stock.canonical,
            period=kline_period,
            limit=kline_limit,
        )
        statuses.append(
            SourceStatus(
                source="mootdx.kline|akshare.kline",
                ok=bool(klines),
                message=None if klines else "kline unavailable",
            )
        )

        profile = await self.get_company_profile(stock.canonical)
        statuses.append(
            SourceStatus(
                source="mootdx.finance|akshare.company_profile",
                ok=profile is not None,
                message=None if profile is not None else "company profile unavailable",
            )
        )

        financials = await self.get_financials(stock.canonical)
        statuses.append(
            SourceStatus(
                source="mootdx.finance",
                ok=financials is not None,
                message=None if financials is not None else "financial adapter pending",
            )
        )

        announcements = await self.get_announcements(
            stock.canonical, limit=announcement_limit
        )
        statuses.append(
            SourceStatus(
                source="cninfo|akshare.announcements",
                ok=bool(announcements),
                message=None if announcements else "announcement unavailable or endpoint missing",
            )
        )

        news = await self.get_news(stock.canonical, limit=news_limit)
        statuses.append(
            SourceStatus(
                source="akshare.news|tavily",
                ok=bool(news),
                message=None if news else "news unavailable or endpoint missing",
            )
        )

        snapshot = AStockSnapshot(
            symbol=stock.canonical,
            code=stock.code,
            exchange=stock.exchange,
            quote=quote if quote is not None else self._cached_quote(cached_snapshot),
            klines=klines if klines else self._cached_klines(cached_snapshot),
            company_profile=(
                profile if profile is not None else self._cached_company_profile(cached_snapshot)
            ),
            financial_summary=(
                financials if financials is not None else self._cached_financials(cached_snapshot)
            ),
            announcements=(
                announcements if announcements else self._cached_announcements(cached_snapshot)
            ),
            news=news if news else self._cached_news(cached_snapshot),
            source_status=statuses,
        )
        cache_fields = self._cache_fallback_fields(
            cached_snapshot=cached_snapshot,
            quote=quote,
            klines=klines,
            profile=profile,
            financials=financials,
            announcements=announcements,
            news=news,
        )
        if cache_fields:
            snapshot.source_status.append(
                SourceStatus(
                    source="cache.snapshot",
                    ok=True,
                    message=f"used cached fields: {', '.join(cache_fields)}",
                )
            )

        self._write_cached_snapshot(snapshot)
        return snapshot

    @staticmethod
    def _read_cached_snapshot(symbol: str) -> AStockSnapshot | None:
        cached = read_json_cache("snapshot", symbol)
        if cached is None:
            return None
        try:
            return AStockSnapshot.model_validate(cached)
        except ValueError as exc:
            logger.warning("Ignoring invalid A-stock snapshot cache for {}: {}", symbol, exc)
            return None

    @staticmethod
    def _write_cached_snapshot(snapshot: AStockSnapshot) -> None:
        has_data = any(
            [
                snapshot.quote is not None,
                bool(snapshot.klines),
                snapshot.company_profile is not None,
                snapshot.financial_summary is not None,
                bool(snapshot.announcements),
                bool(snapshot.news),
            ]
        )
        if not has_data:
            return
        try:
            write_json_cache(
                "snapshot",
                snapshot.symbol,
                snapshot.model_dump(mode="json"),
            )
        except OSError as exc:
            logger.warning("Failed to write A-stock snapshot cache for {}: {}", snapshot.symbol, exc)

    @staticmethod
    def _cached_quote(snapshot: AStockSnapshot | None) -> Quote | None:
        return snapshot.quote if snapshot is not None else None

    @staticmethod
    def _cached_klines(snapshot: AStockSnapshot | None) -> list[Kline]:
        return snapshot.klines if snapshot is not None else []

    @staticmethod
    def _cached_company_profile(snapshot: AStockSnapshot | None) -> CompanyProfile | None:
        return snapshot.company_profile if snapshot is not None else None

    @staticmethod
    def _cached_financials(snapshot: AStockSnapshot | None) -> FinancialSummary | None:
        return snapshot.financial_summary if snapshot is not None else None

    @staticmethod
    def _cached_announcements(snapshot: AStockSnapshot | None) -> list[Announcement]:
        return snapshot.announcements if snapshot is not None else []

    @staticmethod
    def _cached_news(snapshot: AStockSnapshot | None) -> list[NewsItem]:
        return snapshot.news if snapshot is not None else []

    @staticmethod
    def _cache_fallback_fields(
        *,
        cached_snapshot: AStockSnapshot | None,
        quote: Quote | None,
        klines: list[Kline],
        profile: CompanyProfile | None,
        financials: FinancialSummary | None,
        announcements: list[Announcement],
        news: list[NewsItem],
    ) -> list[str]:
        if cached_snapshot is None:
            return []
        fields: list[str] = []
        if quote is None and cached_snapshot.quote is not None:
            fields.append("quote")
        if not klines and cached_snapshot.klines:
            fields.append("klines")
        if profile is None and cached_snapshot.company_profile is not None:
            fields.append("company_profile")
        if financials is None and cached_snapshot.financial_summary is not None:
            fields.append("financial_summary")
        if not announcements and cached_snapshot.announcements:
            fields.append("announcements")
        if not news and cached_snapshot.news:
            fields.append("news")
        return fields


_astock_data_service: AStockDataService | None = None


def get_astock_data_service() -> AStockDataService:
    global _astock_data_service
    if _astock_data_service is None:
        _astock_data_service = AStockDataService()
    return _astock_data_service


def reset_astock_data_service() -> None:
    global _astock_data_service
    _astock_data_service = None




