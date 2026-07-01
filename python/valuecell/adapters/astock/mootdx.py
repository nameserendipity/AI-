"""Mootdx adapter for the A-share data layer.

Mootdx is intended to be the preferred A-share quote/K-line provider because it
uses TongDaXin-compatible market data endpoints. The dependency is optional: if
`mootdx` is not installed or an endpoint fails, callers should fall back to other
adapters through `AStockDataService`.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from .akshare import _to_date, _to_float, _row_to_dict
from .schemas import CompanyProfile, FinancialSummary, Kline, Quote
from .symbols import AStockSymbol, normalize_symbol


class MootdxUnavailableError(RuntimeError):
    """Raised when mootdx is not installed or cannot be initialized."""


class MootdxAStockAdapter:
    """A-share market adapter backed by mootdx."""

    source = "mootdx"

    async def get_quote(self, symbol: str) -> Quote | None:
        stock = normalize_symbol(symbol)
        return await asyncio.to_thread(self._get_quote_sync, stock)

    async def get_kline(
        self,
        symbol: str,
        *,
        period: str = "daily",
        limit: int = 250,
    ) -> list[Kline]:
        stock = normalize_symbol(symbol)
        return await asyncio.to_thread(self._get_kline_sync, stock, period, limit)

    async def get_company_profile(self, symbol: str) -> CompanyProfile | None:
        stock = normalize_symbol(symbol)
        return await asyncio.to_thread(self._get_company_profile_sync, stock)

    async def get_financials(self, symbol: str) -> FinancialSummary | None:
        stock = normalize_symbol(symbol)
        return await asyncio.to_thread(self._get_financials_sync, stock)

    async def get_f10_section(self, symbol: str, section_name: str) -> str | None:
        stock = normalize_symbol(symbol)
        return await asyncio.to_thread(self._get_f10_section_sync, stock, section_name)
    def _client(self):
        try:
            from mootdx.quotes import Quotes
        except Exception as exc:  # noqa: BLE001
            raise MootdxUnavailableError("mootdx is not installed") from exc

        try:
            return Quotes.factory(market="std")
        except TypeError:
            return Quotes.factory("std")

    def _market_code(self, stock: AStockSymbol) -> int:
        return 1 if stock.exchange == "SH" else 0

    def _period_code(self, period: str) -> int:
        normalized = str(period or "daily").lower()
        mapping = {
            "daily": 9,
            "1d": 9,
            "day": 9,
            "weekly": 5,
            "1w": 5,
            "week": 5,
            "monthly": 6,
            "1mo": 6,
            "month": 6,
            "5m": 0,
            "15m": 1,
            "30m": 2,
            "1h": 3,
            "60m": 3,
        }
        return mapping.get(normalized, 9)

    def _get_quote_sync(self, stock: AStockSymbol) -> Quote | None:
        try:
            client = self._client()
            try:
                df = client.quotes(symbol=[stock.code])
            except TypeError:
                df = client.quotes([stock.code])
            if df is None or df.empty:
                return None

            raw = _row_to_dict(df.iloc[0])
            name = raw.get("name") or raw.get("名称") or raw.get("stock_name")
            return Quote(
                symbol=stock.canonical,
                code=stock.code,
                exchange=stock.exchange,
                source=self.source,
                name=str(name or "") or None,
                price=_to_float(
                    raw.get("price")
                    or raw.get("最新价")
                    or raw.get("last")
                    or raw.get("close")
                ),
                change=_to_float(raw.get("涨跌额") or raw.get("change")),
                change_pct=_to_float(raw.get("涨跌幅") or raw.get("change_pct")),
                open=_to_float(raw.get("open") or raw.get("今开")),
                high=_to_float(raw.get("high") or raw.get("最高")),
                low=_to_float(raw.get("low") or raw.get("最低")),
                previous_close=_to_float(raw.get("last_close") or raw.get("昨收")),
                volume=_to_float(raw.get("vol") or raw.get("volume") or raw.get("成交量")),
                amount=_to_float(raw.get("amount") or raw.get("成交额")),
                raw=raw,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Mootdx quote failed for {}: {}", stock.canonical, exc)
            return None

    def _get_kline_sync(self, stock: AStockSymbol, period: str, limit: int) -> list[Kline]:
        try:
            client = self._client()
            market = self._market_code(stock)
            frequency = self._period_code(period)
            count = max(1, min(int(limit or 250), 800))

            try:
                df = client.bars(
                    symbol=stock.code,
                    frequency=frequency,
                    start=0,
                    offset=count,
                )
            except TypeError:
                df = client.bars(stock.code, frequency=frequency, start=0, offset=count)

            if df is None or df.empty:
                return []

            klines: list[Kline] = []
            for _, row in df.tail(count).iterrows():
                raw = _row_to_dict(row)
                trade_date = (
                    raw.get("datetime")
                    or raw.get("date")
                    or raw.get("日期")
                    or raw.get("time")
                )
                if trade_date is None:
                    continue
                klines.append(
                    Kline(
                        symbol=stock.canonical,
                        code=stock.code,
                        exchange=stock.exchange,
                        source=self.source,
                        trade_date=_to_date(str(trade_date)[:10]),
                        interval=period,
                        open=_to_float(raw.get("open") or raw.get("开盘")),
                        close=_to_float(raw.get("close") or raw.get("收盘")),
                        high=_to_float(raw.get("high") or raw.get("最高")),
                        low=_to_float(raw.get("low") or raw.get("最低")),
                        volume=_to_float(raw.get("vol") or raw.get("volume") or raw.get("成交量")),
                        amount=_to_float(raw.get("amount") or raw.get("成交额")),
                        raw=raw,
                    )
                )
            return klines
        except Exception as exc:  # noqa: BLE001
            logger.warning("Mootdx kline failed for {}: {}", stock.canonical, exc)
            return []
    def _get_finance_row(self, stock: AStockSymbol) -> dict[str, Any] | None:
        client = self._client()
        df = client.finance(symbol=stock.code)
        if df is None or df.empty:
            return None
        return _row_to_dict(df.iloc[0])

    def _get_company_profile_sync(self, stock: AStockSymbol) -> CompanyProfile | None:
        try:
            raw = self._get_finance_row(stock)
            if not raw:
                return None
            return CompanyProfile(
                symbol=stock.canonical,
                code=stock.code,
                exchange=stock.exchange,
                source=f"{self.source}.finance",
                listing_date=str(raw.get("ipo_date") or "") or None,
                total_share_capital=_to_float(raw.get("zongguben")),
                circulating_share_capital=_to_float(raw.get("liutongguben")),
                raw=raw,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Mootdx company profile failed for {}: {}", stock.canonical, exc)
            return None

    def _get_financials_sync(self, stock: AStockSymbol) -> FinancialSummary | None:
        try:
            raw = self._get_finance_row(stock)
            if not raw:
                return None
            revenue = _to_float(raw.get("zhuyingshouru"))
            net_profit = _to_float(raw.get("jinglirun") or raw.get("shuihoulirun"))
            net_assets = _to_float(raw.get("jingzichan"))
            roe = None
            if net_profit is not None and net_assets:
                roe = net_profit / net_assets * 100
            return FinancialSummary(
                symbol=stock.canonical,
                code=stock.code,
                exchange=stock.exchange,
                source=f"{self.source}.finance",
                report_date=str(raw.get("updated_date") or "") or None,
                revenue=revenue,
                net_profit=net_profit,
                roe=roe,
                raw=raw,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Mootdx financials failed for {}: {}", stock.canonical, exc)
            return None

    def _get_f10_section_sync(self, stock: AStockSymbol, section_name: str) -> str | None:
        try:
            client = self._client()
            text = client.F10(symbol=stock.code, name=section_name)
            if not text:
                return None
            return str(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Mootdx F10 section {} failed for {}: {}",
                section_name,
                stock.canonical,
                exc,
            )
            return None

