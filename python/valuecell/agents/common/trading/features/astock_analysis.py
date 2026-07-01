"""A-share analysis feature pipeline for PromptBasedStrategyAgent."""

from __future__ import annotations

import json

from loguru import logger

from valuecell.agents.common.trading.constants import (
    FEATURE_GROUP_BY_KEY,
    FEATURE_GROUP_BY_MARKET_SNAPSHOT,
)
from valuecell.agents.common.trading.features.interfaces import BaseFeaturesPipeline
from valuecell.agents.common.trading.models import (
    FeatureVector,
    FeaturesPipelineResult,
    InstrumentRef,
    UserRequest,
)
from valuecell.server.services.astock import AStockAnalysisService
from valuecell.utils.ts import get_current_timestamp_ms

ASTOCK_ANALYSIS_GROUP = "astock_analysis"
ASTOCK_RISK_GROUP = "risk_flags"


class AStockAnalysisFeaturesPipeline(BaseFeaturesPipeline):
    """Build strategy features from the local A-share analysis service.

    This pipeline lets PromptBasedStrategyAgent consume the same structured
    A-share data layer as AStockAnalysisAgent. It avoids CCXT market fetches for
    A-share symbols and exposes both a market snapshot and a compact analysis
    vector to the existing LLM composer.
    """

    def __init__(
        self,
        *,
        request: UserRequest,
        analysis_service: AStockAnalysisService | None = None,
        kline_limit: int = 120,
        news_limit: int = 10,
        announcement_limit: int = 10,
    ) -> None:
        self._request = request
        self._analysis_service = analysis_service or AStockAnalysisService()
        self._kline_limit = kline_limit
        self._news_limit = news_limit
        self._announcement_limit = announcement_limit

    async def build(self) -> FeaturesPipelineResult:
        features: list[FeatureVector] = []
        for symbol in self._request.trading_config.symbols:
            try:
                report = await self._analysis_service.analyze_symbol(
                    symbol,
                    kline_limit=self._kline_limit,
                    news_limit=self._news_limit,
                    announcement_limit=self._announcement_limit,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to build A-share analysis features for {}: {}", symbol, exc)
                continue

            instrument = InstrumentRef(
                symbol=report.symbol,
                exchange_id="astock",
            )
            ts = get_current_timestamp_ms()
            features.append(self._build_market_feature(ts, instrument, report))
            features.append(self._build_analysis_feature(ts, instrument, report))

        return FeaturesPipelineResult(features=features)

    def _build_market_feature(self, ts: int, instrument: InstrumentRef, report) -> FeatureVector:
        values: dict[str, float | str | int | list[float | str | int]] = {}
        tech = report.technical
        if tech.latest_close is not None:
            values["price.last"] = float(tech.latest_close)
            values["price.close"] = float(tech.latest_close)
        if tech.recent_high is not None:
            values["price.high"] = float(tech.recent_high)
        if tech.recent_low is not None:
            values["price.low"] = float(tech.recent_low)
        if tech.change_5d_pct is not None:
            values["price.change_pct"] = float(tech.change_5d_pct)

        return FeatureVector(
            ts=ts,
            instrument=instrument,
            values=values,
            meta={
                FEATURE_GROUP_BY_KEY: FEATURE_GROUP_BY_MARKET_SNAPSHOT,
                "source": "astock_analysis_service",
            },
        )

    def _build_analysis_feature(self, ts: int, instrument: InstrumentRef, report) -> FeatureVector:
        tech = report.technical
        sentiment = report.sentiment
        values: dict[str, float | str | int | list[float | str | int]] = {
            "analysis.bias": report.bias,
            "analysis.confidence": float(report.confidence),
            "analysis.summary": report.summary,
            "analysis.report_json": json.dumps(report.model_dump(mode="json"), ensure_ascii=False),
            "technical.trend": tech.trend,
            "sentiment.bias": sentiment.bias,
            "sentiment.score": int(sentiment.score),
            "news.count": int(sentiment.news_count),
            "announcement.count": int(sentiment.announcement_count),
            "risk.flags": report.risk_flags,
            "key.points": report.key_points,
        }
        optional_values = {
            "technical.ma5": tech.ma5,
            "technical.ma20": tech.ma20,
            "technical.ma60": tech.ma60,
            "technical.change_5d_pct": tech.change_5d_pct,
            "technical.change_20d_pct": tech.change_20d_pct,
            "technical.support": tech.support,
            "technical.resistance": tech.resistance,
            "technical.range_position_pct": tech.range_position_pct,
            "technical.average_amplitude_pct": tech.average_amplitude_pct,
        }
        for key, value in optional_values.items():
            if value is not None:
                values[key] = float(value)

        return FeatureVector(
            ts=ts,
            instrument=instrument,
            values=values,
            meta={
                FEATURE_GROUP_BY_KEY: ASTOCK_ANALYSIS_GROUP,
                "source": "astock_analysis_service",
            },
        )
