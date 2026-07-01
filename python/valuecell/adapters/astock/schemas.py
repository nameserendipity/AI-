"""Standard schemas for the A-share data layer."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AStockExchange = Literal["SH", "SZ", "BJ"]
AStockView = Literal["bullish", "bearish", "neutral", "mixed", "unknown"]


class SourceStatus(BaseModel):
    source: str
    ok: bool
    message: str | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AStockBase(BaseModel):
    symbol: str = Field(..., description="Canonical symbol, e.g. 300750.SZ")
    code: str
    exchange: AStockExchange
    source: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class Quote(AStockBase):
    name: str | None = None
    price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    previous_close: float | None = None
    volume: float | None = None
    amount: float | None = None
    turnover_rate: float | None = None
    pe_dynamic: float | None = None
    pb: float | None = None
    total_market_cap: float | None = None
    circulating_market_cap: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class Kline(AStockBase):
    trade_date: date
    interval: str = "daily"
    open: float | None = None
    close: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    amount: float | None = None
    amplitude: float | None = None
    change_pct: float | None = None
    change: float | None = None
    turnover_rate: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class CompanyProfile(AStockBase):
    name: str | None = None
    industry: str | None = None
    listing_date: str | None = None
    total_share_capital: float | None = None
    circulating_share_capital: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class FinancialSummary(AStockBase):
    report_date: str | None = None
    revenue: float | None = None
    net_profit: float | None = None
    roe: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class Announcement(AStockBase):
    title: str
    publish_time: str | None = None
    url: str | None = None
    category: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class NewsItem(AStockBase):
    title: str
    publish_time: str | None = None
    url: str | None = None
    summary: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class AStockSnapshot(BaseModel):
    symbol: str
    code: str
    exchange: AStockExchange
    quote: Quote | None = None
    klines: list[Kline] = Field(default_factory=list)
    company_profile: CompanyProfile | None = None
    financial_summary: FinancialSummary | None = None
    announcements: list[Announcement] = Field(default_factory=list)
    news: list[NewsItem] = Field(default_factory=list)
    source_status: list[SourceStatus] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
