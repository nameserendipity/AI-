"""AkShare adapter for the A-share data layer.

The adapter intentionally wraps only a small MVP surface first: quote, K-line,
company profile, announcements, and news. Each method returns standardized
schemas so agents do not depend on AkShare's raw DataFrame columns.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any

from loguru import logger

from .schemas import Announcement, CompanyProfile, Kline, NewsItem, Quote
from .symbols import AStockSymbol, normalize_symbol


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if value == "" or str(value).lower() in {"nan", "none", "--", "-"}:
            return None
        return float(value)
    except Exception:
        return None


def _to_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value}")


def _row_to_dict(row: Any) -> dict[str, Any]:
    try:
        return {str(k): v for k, v in row.to_dict().items()}
    except Exception:
        return {}


class AkShareAStockAdapter:
    """A-share adapter backed by AkShare."""

    source = "akshare"

    async def get_quote(self, symbol: str) -> Quote | None:
        stock = normalize_symbol(symbol)
        return await asyncio.to_thread(self._get_quote_sync, stock)

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
        stock = normalize_symbol(symbol)
        return await asyncio.to_thread(
            self._get_kline_sync,
            stock,
            period,
            start_date,
            end_date,
            adjust,
            limit,
        )

    async def get_company_profile(self, symbol: str) -> CompanyProfile | None:
        stock = normalize_symbol(symbol)
        return await asyncio.to_thread(self._get_company_profile_sync, stock)

    async def get_announcements(self, symbol: str, *, limit: int = 20) -> list[Announcement]:
        stock = normalize_symbol(symbol)
        return await asyncio.to_thread(self._get_announcements_sync, stock, limit)

    async def get_news(self, symbol: str, *, limit: int = 20) -> list[NewsItem]:
        stock = normalize_symbol(symbol)
        return await asyncio.to_thread(self._get_news_sync, stock, limit)

    def _get_quote_sync(self, stock: AStockSymbol) -> Quote | None:
        try:
            import akshare as ak

            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                return None
            rows = df[df["代码"].astype(str).str.zfill(6) == stock.code]
            if rows.empty:
                return None
            raw = _row_to_dict(rows.iloc[0])
            return Quote(
                symbol=stock.canonical,
                code=stock.code,
                exchange=stock.exchange,
                source=self.source,
                name=str(raw.get("名称") or "") or None,
                price=_to_float(raw.get("最新价")),
                change=_to_float(raw.get("涨跌额")),
                change_pct=_to_float(raw.get("涨跌幅")),
                open=_to_float(raw.get("今开")),
                high=_to_float(raw.get("最高")),
                low=_to_float(raw.get("最低")),
                previous_close=_to_float(raw.get("昨收")),
                volume=_to_float(raw.get("成交量")),
                amount=_to_float(raw.get("成交额")),
                turnover_rate=_to_float(raw.get("换手率")),
                pe_dynamic=_to_float(raw.get("市盈率-动态")),
                pb=_to_float(raw.get("市净率")),
                total_market_cap=_to_float(raw.get("总市值")),
                circulating_market_cap=_to_float(raw.get("流通市值")),
                raw=raw,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("AkShare quote failed for {}: {}", stock.canonical, exc)
            return self._get_quote_from_latest_kline(stock)

    def _get_quote_from_latest_kline(self, stock: AStockSymbol) -> Quote | None:
        """Fallback quote from latest daily K-line when spot endpoint is unavailable."""
        klines = self._get_kline_sync(
            stock=stock,
            period="daily",
            start_date=None,
            end_date=None,
            adjust="",
            limit=1,
        )
        if not klines:
            return None
        latest = klines[-1]
        return Quote(
            symbol=stock.canonical,
            code=stock.code,
            exchange=stock.exchange,
            source=f"{self.source}.kline_fallback",
            price=latest.close,
            change=latest.change,
            change_pct=latest.change_pct,
            open=latest.open,
            high=latest.high,
            low=latest.low,
            volume=latest.volume,
            amount=latest.amount,
            turnover_rate=latest.turnover_rate,
            raw={"fallback": "latest_daily_kline", **latest.raw},
        )

    def _get_kline_sync(
        self,
        stock: AStockSymbol,
        period: str,
        start_date: date | str | None,
        end_date: date | str | None,
        adjust: str,
        limit: int,
    ) -> list[Kline]:
        try:
            import akshare as ak

            today = date.today()
            start = _to_date(start_date) if start_date else today - timedelta(days=500)
            end = _to_date(end_date) if end_date else today
            df = ak.stock_zh_a_hist(
                symbol=stock.akshare_code,
                period=period,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust=adjust,
            )
            if df is None or df.empty:
                return []
            if limit > 0:
                df = df.tail(limit)

            klines: list[Kline] = []
            for _, row in df.iterrows():
                raw = _row_to_dict(row)
                klines.append(
                    Kline(
                        symbol=stock.canonical,
                        code=stock.code,
                        exchange=stock.exchange,
                        source=self.source,
                        trade_date=_to_date(raw.get("日期")),
                        interval=period,
                        open=_to_float(raw.get("开盘")),
                        close=_to_float(raw.get("收盘")),
                        high=_to_float(raw.get("最高")),
                        low=_to_float(raw.get("最低")),
                        volume=_to_float(raw.get("成交量")),
                        amount=_to_float(raw.get("成交额")),
                        amplitude=_to_float(raw.get("振幅")),
                        change_pct=_to_float(raw.get("涨跌幅")),
                        change=_to_float(raw.get("涨跌额")),
                        turnover_rate=_to_float(raw.get("换手率")),
                        raw=raw,
                    )
                )
            return klines
        except Exception as exc:  # noqa: BLE001
            logger.warning("AkShare kline failed for {}: {}", stock.canonical, exc)
            return []

    def _get_company_profile_sync(self, stock: AStockSymbol) -> CompanyProfile | None:
        try:
            import akshare as ak

            df = ak.stock_individual_info_em(symbol=stock.akshare_code)
            if df is None or df.empty:
                return None
            raw_items = {}
            for _, row in df.iterrows():
                item = str(row.get("item") or row.get("项目") or "").strip()
                value = row.get("value") if "value" in row else row.get("值")
                if item:
                    raw_items[item] = value
            return CompanyProfile(
                symbol=stock.canonical,
                code=stock.code,
                exchange=stock.exchange,
                source=self.source,
                name=str(raw_items.get("股票简称") or raw_items.get("简称") or "") or None,
                industry=str(raw_items.get("行业") or "") or None,
                listing_date=str(raw_items.get("上市时间") or "") or None,
                total_share_capital=_to_float(raw_items.get("总股本")),
                circulating_share_capital=_to_float(raw_items.get("流通股")),
                raw=raw_items,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("AkShare profile failed for {}: {}", stock.canonical, exc)
            return None

    def _get_announcements_sync(self, stock: AStockSymbol, limit: int) -> list[Announcement]:
        """Best-effort announcement retrieval.

        AkShare announcement APIs vary between versions. This method tries common
        endpoints and returns an empty list when unavailable.
        """
        try:
            import akshare as ak

            candidates = []
            if hasattr(ak, "stock_notice_report"):
                candidates.append(lambda: ak.stock_notice_report(symbol=stock.akshare_code))
            if hasattr(ak, "stock_zh_a_disclosure_report_cninfo"):
                candidates.append(
                    lambda: ak.stock_zh_a_disclosure_report_cninfo(symbol=stock.akshare_code)
                )

            for fetch in candidates:
                try:
                    df = fetch()
                    if df is not None and not df.empty:
                        return self._parse_announcements(stock, df, limit)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("AkShare announcement endpoint failed: {}", exc)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning("AkShare announcements failed for {}: {}", stock.canonical, exc)
            return []

    def _parse_announcements(self, stock: AStockSymbol, df: Any, limit: int) -> list[Announcement]:
        records: list[Announcement] = []
        for _, row in df.head(max(limit, 1)).iterrows():
            raw = _row_to_dict(row)
            title = str(
                raw.get("公告标题")
                or raw.get("标题")
                or raw.get("announcementTitle")
                or raw.get("title")
                or ""
            ).strip()
            if not title:
                continue
            records.append(
                Announcement(
                    symbol=stock.canonical,
                    code=stock.code,
                    exchange=stock.exchange,
                    source=self.source,
                    title=title,
                    publish_time=str(
                        raw.get("公告时间")
                        or raw.get("公告日期")
                        or raw.get("publish_time")
                        or raw.get("date")
                        or ""
                    )
                    or None,
                    url=str(raw.get("公告链接") or raw.get("url") or raw.get("URL") or "")
                    or None,
                    category=str(raw.get("公告类型") or raw.get("category") or "") or None,
                    raw=raw,
                )
            )
        return records

    def _get_news_sync(self, stock: AStockSymbol, limit: int) -> list[NewsItem]:
        try:
            import akshare as ak

            if not hasattr(ak, "stock_news_em"):
                return []
            df = ak.stock_news_em(symbol=stock.akshare_code)
            if df is None or df.empty:
                return []
            records: list[NewsItem] = []
            for _, row in df.head(max(limit, 1)).iterrows():
                raw = _row_to_dict(row)
                title = str(raw.get("新闻标题") or raw.get("标题") or raw.get("title") or "").strip()
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
                            raw.get("发布时间") or raw.get("时间") or raw.get("date") or ""
                        )
                        or None,
                        url=str(raw.get("新闻链接") or raw.get("链接") or raw.get("url") or "")
                        or None,
                        summary=str(raw.get("新闻内容") or raw.get("摘要") or "") or None,
                        raw=raw,
                    )
                )
            return records
        except Exception as exc:  # noqa: BLE001
            logger.warning("AkShare news failed for {}: {}", stock.canonical, exc)
            return []

