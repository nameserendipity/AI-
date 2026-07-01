"""Bridge A-share data into the legacy watchlist API shape."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from valuecell.adapters.astock.symbols import AStockSymbolError, normalize_symbol

from .astock_data_service import AStockDataService


A_STOCK_INTERNAL_EXCHANGES = {"SSE", "SZSE", "BSE"}


def is_astock_ticker(ticker: str) -> bool:
    """Return true when ticker can be handled by the A-share data layer."""
    try:
        normalize_symbol(ticker)
    except AStockSymbolError:
        return False
    return True


def astock_preview_symbol(ticker: str) -> str | None:
    """Extract the six-digit symbol for frontend strategy-preview routes."""
    try:
        return normalize_symbol(ticker).code
    except AStockSymbolError:
        return None


def _format_cny(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"¥{value:,.2f}"


def _format_percent(value: float | None) -> str | None:
    if value is None:
        return None
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


async def get_astock_price_for_watchlist(ticker: str) -> dict[str, Any] | None:
    """Return A-share quote in the legacy AssetPriceData-compatible dict."""
    try:
        stock = normalize_symbol(ticker)
    except AStockSymbolError:
        return None

    quote = await AStockDataService().get_quote(stock.canonical)
    if quote is None or quote.price is None:
        logger.warning("A-share quote unavailable for {}", stock.canonical)
        return None

    return {
        "success": True,
        "ticker": stock.internal_ticker,
        "price": float(quote.price),
        "price_formatted": _format_cny(quote.price),
        "currency": "CNY",
        "timestamp": quote.fetched_at.isoformat(),
        "volume": float(quote.volume) if quote.volume is not None else None,
        "open_price": float(quote.open) if quote.open is not None else None,
        "high_price": float(quote.high) if quote.high is not None else None,
        "low_price": float(quote.low) if quote.low is not None else None,
        "close_price": float(quote.price),
        "change": float(quote.change) if quote.change is not None else None,
        "change_percent": (
            float(quote.change_pct) if quote.change_pct is not None else None
        ),
        "change_percent_formatted": _format_percent(quote.change_pct),
        "market_cap": (
            float(quote.total_market_cap)
            if quote.total_market_cap is not None
            else None
        ),
        "market_cap_formatted": _format_cny(quote.total_market_cap)
        if quote.total_market_cap is not None
        else None,
        "source": quote.source,
    }


async def get_astock_detail_for_watchlist(ticker: str) -> dict[str, Any] | None:
    """Return A-share profile in the legacy AssetDetailData-compatible dict."""
    try:
        stock = normalize_symbol(ticker)
    except AStockSymbolError:
        return None

    service = AStockDataService()
    profile = await service.get_company_profile(stock.canonical)
    quote = await service.get_quote(stock.canonical)
    name = None
    industry = None
    if profile is not None:
        name = profile.name
        industry = profile.industry
    if not name and quote is not None:
        name = quote.name

    display_name = name or stock.code
    now = datetime.utcnow().isoformat()
    return {
        "success": True,
        "ticker": stock.internal_ticker,
        "asset_type": "stock",
        "asset_type_display": "股票",
        "names": {
            "zh-CN": display_name,
            "zh_CN": display_name,
            "en-US": display_name,
        },
        "display_name": display_name,
        "descriptions": {},
        "market_info": {
            "exchange": stock.internal_ticker.split(":", 1)[0],
            "country": "CN",
            "currency": "CNY",
            "timezone": "Asia/Shanghai",
            "trading_hours": "09:30-11:30, 13:00-15:00",
            "market_status": "unknown",
        },
        "source_mappings": {"astock": stock.canonical},
        "properties": {
            "sector": "",
            "industry": industry or "",
            "market_cap": quote.total_market_cap if quote else None,
            "pe_ratio": quote.pe_dynamic if quote else None,
            "dividend_yield": None,
            "beta": None,
            "website": "",
            "business_summary": "",
            "listing_date": profile.listing_date if profile else None,
        },
        "created_at": now,
        "updated_at": now,
        "is_active": True,
    }
