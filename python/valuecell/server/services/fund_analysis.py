"""Fund analysis service — aggregates individual stock analyses into a fund-level score."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field
from loguru import logger

from valuecell.server.db.models.fund import Fund, FundHolding
from valuecell.server.services.astock.analysis import (
    AStockAnalysisReport,
    AStockAnalysisService,
    AStockAnalyzer,
    AnalysisBias,
)
from valuecell.server.services.astock.astock_data_service import AStockDataService


class HoldingAnalysisResult(BaseModel):
    """Per-holding analysis result."""

    ticker: str
    name: Optional[str] = None
    weight: float = 0.0
    company_name: Optional[str] = None
    bias: AnalysisBias = "unknown"
    confidence: float = 0.0
    score: float = 0.0
    technical_trend: AnalysisBias = "unknown"
    sentiment_bias: AnalysisBias = "unknown"
    summary: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class FundAnalysisResult(BaseModel):
    """Result of a complete fund analysis."""

    fund_id: int
    fund_name: str
    fund_code: Optional[str] = None
    total_score: float = 0.0
    overall_bias: AnalysisBias = "unknown"
    suggestion: str = ""
    weighted_confidence: float = 0.0
    holdings_analyzed: int = 0
    holdings_total: int = 0
    holding_results: List[HoldingAnalysisResult] = Field(default_factory=list)
    aggregated_key_points: List[str] = Field(default_factory=list)
    aggregated_risk_flags: List[str] = Field(default_factory=list)
    analyzed_at: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))


def _holding_score(bias: AnalysisBias) -> float:
    """Map a bias to a numerical score component."""
    mapping = {
        "bullish": 40.0,
        "mixed": 10.0,
        "neutral": 0.0,
        "bearish": -20.0,
        "unknown": 0.0,
    }
    return mapping.get(bias, 0.0)


def _bias_from_score(score: float) -> AnalysisBias:
    if score >= 30:
        return "bullish"
    if score >= 10:
        return "mixed"
    if score >= -5:
        return "neutral"
    return "bearish"


def _suggestion_from_score(score: float) -> str:
    if score >= 60.0:
        return "建议加仓 — 多数成分股技术面与消息面均偏积极"
    if score >= 30.0:
        return "适合持有 — 整体中性偏乐观，观察后续变化"
    if score >= 0.0:
        return "观望 — 个别成分股存在风险，等待信号明确"
    return "建议减仓/回避 — 成分股整体偏弱"


def _merge_key_points(results: List[HoldingAnalysisResult]) -> List[str]:
    points: List[str] = []
    for r in results:
        if r.error:
            points.append(f"{r.name or r.ticker}：分析失败（{r.error}）")
            continue
        if r.key_points:
            sharp = r.key_points[:2]
            points.append(f"{r.name or r.ticker}：{'；'.join(sharp)}")
    return points


def _merge_risk_flags(results: List[HoldingAnalysisResult]) -> List[str]:
    risks: List[str] = []
    for r in results:
        if r.risk_flags:
            for f in r.risk_flags[:2]:
                risks.append(f"{r.name or r.ticker}：{f}")
    return risks


class FundAnalysisService:
    """Analyze a fund by aggregating analyses of its holdings."""

    def __init__(
        self,
        analysis_service: Optional[AStockAnalysisService] = None,
    ) -> None:
        self.analysis_service = analysis_service or AStockAnalysisService()

    async def analyze_fund(
        self,
        fund: Fund,
        holdings: List[FundHolding],
    ) -> FundAnalysisResult:
        """Analyze a fund by scoring each of its holdings.

        Args:
            fund: The fund to analyze.
            holdings: The fund's stock holdings.

        Returns:
            A FundAnalysisResult with per-holding scores and aggregated metrics.
        """
        total_weight = sum(h.weight for h in holdings) or 1.0

        holding_results: List[HoldingAnalysisResult] = []
        total_weighted_score = 0.0
        total_weighted_confidence = 0.0

        for holding in holdings:
            result = await self._analyze_holding(holding)
            holding_results.append(result)

            w = result.weight
            s = result.score
            c = result.confidence

            # Confidence-adjusted weight
            effective_weight = w
            if c > 0.7:
                effective_weight = w * 1.2
            elif c < 0.3:
                effective_weight = w * 0.6

            total_weighted_score += s * effective_weight
            total_weighted_confidence += c * w

        # Normalize score to 0-100 range
        # Raw score range: bearish(-20) to bullish(+40) per holding
        # With weights summed… shift so 0 is neutral-ish
        max_possible = total_weight * 40.0  # all bullish
        min_possible = total_weight * -20.0  # all bearish
        normalized = (
            (total_weighted_score - min_possible) / (max_possible - min_possible) * 100
            if max_possible != min_possible
            else 50.0
        )
        normalized = max(0.0, min(100.0, normalized))

        avg_confidence = total_weighted_confidence / total_weight

        return FundAnalysisResult(
            fund_id=fund.id,
            fund_name=fund.name,
            fund_code=fund.code,
            total_score=round(normalized, 1),
            overall_bias=_bias_from_score(normalized),
            suggestion=_suggestion_from_score(normalized),
            weighted_confidence=round(avg_confidence, 2),
            holdings_analyzed=len(holding_results),
            holdings_total=len(holdings),
            holding_results=holding_results,
            aggregated_key_points=_merge_key_points(holding_results),
            aggregated_risk_flags=_merge_risk_flags(holding_results),
        )

    async def _analyze_holding(
        self, holding: FundHolding
    ) -> HoldingAnalysisResult:
        """Analyze a single holding stock."""
        try:
            report = await self.analysis_service.analyze_symbol(holding.ticker)
            bias = report.bias
            confidence = report.confidence
            score = _holding_score(bias)

            # Adjust score by confidence
            score = score * (0.5 + confidence * 0.5)

            return HoldingAnalysisResult(
                ticker=holding.ticker,
                name=holding.name,
                weight=holding.weight,
                company_name=report.name,
                bias=bias,
                confidence=confidence,
                score=round(score, 1),
                technical_trend=report.technical.trend,
                sentiment_bias=report.sentiment.bias,
                summary=report.summary,
                key_points=report.key_points,
                risk_flags=report.risk_flags,
            )
        except Exception as exc:
            logger.warning("Failed to analyze holding {}: {}", holding.ticker, exc)
            return HoldingAnalysisResult(
                ticker=holding.ticker,
                name=holding.name,
                weight=holding.weight,
                error=str(exc),
            )
