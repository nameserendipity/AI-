"""Rule-based A-share analysis models and service."""

from __future__ import annotations

import re
from datetime import datetime
from statistics import mean
from typing import Literal

from pydantic import BaseModel, Field

from valuecell.adapters.astock.schemas import AStockSnapshot, Kline, NewsItem
from valuecell.adapters.astock.symbols import normalize_symbol
from valuecell.server.services.astock.astock_data_service import AStockDataService

AnalysisBias = Literal["bullish", "bearish", "neutral", "mixed", "unknown"]

POSITIVE_KEYWORDS = (
    "增长",
    "上涨",
    "上调",
    "突破",
    "中标",
    "回购",
    "增持",
    "盈利",
    "利好",
    "扩产",
    "创新高",
)
NEGATIVE_KEYWORDS = (
    "下跌",
    "下降",
    "下调",
    "减持",
    "亏损",
    "处罚",
    "诉讼",
    "风险",
    "终止",
    "暴跌",
    "利空",
)


class AStockTechnicalView(BaseModel):
    latest_close: float | None = None
    ma5: float | None = None
    ma20: float | None = None
    ma60: float | None = None
    change_5d_pct: float | None = None
    change_20d_pct: float | None = None
    recent_low: float | None = None
    recent_high: float | None = None
    support: float | None = None
    resistance: float | None = None
    range_position_pct: float | None = None
    average_amplitude_pct: float | None = None
    trend: AnalysisBias = "unknown"


class AStockSentimentView(BaseModel):
    bias: AnalysisBias = "unknown"
    score: int = 0
    positive_hits: list[str] = Field(default_factory=list)
    negative_hits: list[str] = Field(default_factory=list)
    news_count: int = 0
    announcement_count: int = 0


class AStockAnalysisReport(BaseModel):
    symbol: str
    code: str
    exchange: str
    name: str | None = None
    bias: AnalysisBias = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str
    technical: AStockTechnicalView
    sentiment: AStockSentimentView
    key_points: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    source_status: list[str] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class AStockAnalyzer:
    """Convert A-share snapshots into deterministic analysis reports."""

    def analyze(self, snapshot: AStockSnapshot) -> AStockAnalysisReport:
        technical = self._build_technical_view(snapshot.klines)
        sentiment = self._build_sentiment_view(snapshot)
        bias, confidence = self._combine_bias(technical, sentiment)
        key_points = self._build_key_points(snapshot, technical, sentiment)
        risk_flags = self._build_risk_flags(snapshot, technical, sentiment)
        source_status = [
            f"{status.source}: {'ok' if status.ok else 'failed'}"
            + (f" ({status.message})" if status.message else "")
            for status in snapshot.source_status
        ]
        name = self._resolve_name(snapshot)
        summary = self._build_summary(snapshot, name, bias, confidence, technical, sentiment)
        return AStockAnalysisReport(
            symbol=snapshot.symbol,
            code=snapshot.code,
            exchange=snapshot.exchange,
            name=name,
            bias=bias,
            confidence=confidence,
            summary=summary,
            technical=technical,
            sentiment=sentiment,
            key_points=key_points,
            risk_flags=risk_flags,
            source_status=source_status,
        )

    def to_markdown(self, report: AStockAnalysisReport) -> str:
        title_name = f"{report.name} " if report.name else ""
        lines = [
            f"# A股分析：{title_name}{report.symbol}",
            "",
            f"**综合倾向**：{report.bias}  ",
            f"**置信度**：{report.confidence:.0%}  ",
            f"**摘要**：{report.summary}",
            "",
            "## 技术面",
            f"- 最新收盘/价格：{self._fmt(report.technical.latest_close)}",
            f"- MA5 / MA20 / MA60：{self._fmt(report.technical.ma5)} / "
            f"{self._fmt(report.technical.ma20)} / {self._fmt(report.technical.ma60)}",
            f"- 5日/20日涨跌：{self._fmt_pct(report.technical.change_5d_pct)} / "
            f"{self._fmt_pct(report.technical.change_20d_pct)}",
            f"- 支撑/压力：{self._fmt(report.technical.support)} / "
            f"{self._fmt(report.technical.resistance)}",
            "",
            "## 消息面",
            f"- 新闻数/公告数：{report.sentiment.news_count} / "
            f"{report.sentiment.announcement_count}",
            f"- 情绪倾向：{report.sentiment.bias}，分数 {report.sentiment.score}",
            "",
            "## 关键点",
        ]
        lines.extend(f"- {point}" for point in report.key_points)
        lines.append("")
        lines.append("## 风险提示")
        lines.extend(f"- {risk}" for risk in report.risk_flags or ["暂无明显风险信号。"])
        lines.append("")
        lines.append("> 这是数据分析结果，不是投资建议，也不会自动下单。")
        return "\n".join(lines)

    def _build_technical_view(self, klines: list[Kline]) -> AStockTechnicalView:
        usable = [item for item in klines if item.close is not None]
        if not usable:
            return AStockTechnicalView()
        closes = [float(item.close) for item in usable]
        latest = closes[-1]
        highs = [float(item.high) for item in usable[-20:] if item.high is not None]
        lows = [float(item.low) for item in usable[-20:] if item.low is not None]
        amplitudes = [
            float(item.amplitude)
            for item in usable[-20:]
            if item.amplitude is not None
        ]
        recent_high = max(highs) if highs else None
        recent_low = min(lows) if lows else None
        ma5 = _moving_average(closes, 5)
        ma20 = _moving_average(closes, 20)
        ma60 = _moving_average(closes, 60)
        change_5d = _period_change(closes, 5)
        change_20d = _period_change(closes, 20)
        range_position = _range_position(latest, recent_low, recent_high)
        trend = self._trend_from_mas(latest, ma5, ma20, ma60, change_20d)
        return AStockTechnicalView(
            latest_close=latest,
            ma5=ma5,
            ma20=ma20,
            ma60=ma60,
            change_5d_pct=change_5d,
            change_20d_pct=change_20d,
            recent_low=recent_low,
            recent_high=recent_high,
            support=recent_low,
            resistance=recent_high,
            range_position_pct=range_position,
            average_amplitude_pct=mean(amplitudes) if amplitudes else None,
            trend=trend,
        )

    def _trend_from_mas(
        self,
        latest: float,
        ma5: float | None,
        ma20: float | None,
        ma60: float | None,
        change_20d: float | None,
    ) -> AnalysisBias:
        bullish_votes = 0
        bearish_votes = 0
        for ma in (ma5, ma20, ma60):
            if ma is None:
                continue
            if latest > ma:
                bullish_votes += 1
            elif latest < ma:
                bearish_votes += 1
        if change_20d is not None:
            if change_20d > 5:
                bullish_votes += 1
            elif change_20d < -5:
                bearish_votes += 1
        if bullish_votes >= bearish_votes + 2:
            return "bullish"
        if bearish_votes >= bullish_votes + 2:
            return "bearish"
        if bullish_votes and bearish_votes:
            return "mixed"
        return "neutral"

    def _build_sentiment_view(self, snapshot: AStockSnapshot) -> AStockSentimentView:
        texts: list[str] = []
        texts.extend(item.title for item in snapshot.news)
        texts.extend(item.title for item in snapshot.announcements)
        positive_hits = _keyword_hits(texts, POSITIVE_KEYWORDS)
        negative_hits = _keyword_hits(texts, NEGATIVE_KEYWORDS)
        score = len(positive_hits) - len(negative_hits)
        if score >= 2:
            bias: AnalysisBias = "bullish"
        elif score <= -2:
            bias = "bearish"
        elif score != 0:
            bias = "mixed"
        else:
            bias = "neutral" if texts else "unknown"
        return AStockSentimentView(
            bias=bias,
            score=score,
            positive_hits=positive_hits[:8],
            negative_hits=negative_hits[:8],
            news_count=len(snapshot.news),
            announcement_count=len(snapshot.announcements),
        )

    def _combine_bias(
        self, technical: AStockTechnicalView, sentiment: AStockSentimentView
    ) -> tuple[AnalysisBias, float]:
        tech_weight = _bias_score(technical.trend) * 2
        sentiment_weight = _bias_score(sentiment.bias)
        total = tech_weight + sentiment_weight
        confidence = min(0.85, 0.45 + abs(total) * 0.1)
        if total >= 2:
            return "bullish", confidence
        if total <= -2:
            return "bearish", confidence
        if technical.trend == "unknown" and sentiment.bias == "unknown":
            return "unknown", 0.0
        if technical.trend != sentiment.bias and sentiment.bias not in ("neutral", "unknown"):
            return "mixed", 0.5
        return "neutral", 0.45

    def _build_key_points(
        self,
        snapshot: AStockSnapshot,
        technical: AStockTechnicalView,
        sentiment: AStockSentimentView,
    ) -> list[str]:
        points: list[str] = []
        if technical.latest_close is not None:
            points.append(f"最新价格/收盘价约 {technical.latest_close:.2f}。")
        if technical.change_5d_pct is not None:
            points.append(f"近5个交易日涨跌幅约 {technical.change_5d_pct:.2f}%。")
        if technical.range_position_pct is not None:
            points.append(f"价格位于近20日区间约 {technical.range_position_pct:.0f}% 分位。")
        if snapshot.financial_summary is not None:
            fin = snapshot.financial_summary
            if fin.net_profit is not None:
                points.append(f"最近财务摘要净利润约 {fin.net_profit:.2f}。")
            if fin.roe is not None:
                points.append(f"估算 ROE 约 {fin.roe:.2f}%。")
        if sentiment.positive_hits:
            points.append("正面关键词：" + "、".join(sentiment.positive_hits[:3]) + "。")
        if sentiment.negative_hits:
            points.append("负面关键词：" + "、".join(sentiment.negative_hits[:3]) + "。")
        return points or ["当前可用数据有限，建议先补充行情和公告数据。"]

    def _build_risk_flags(
        self,
        snapshot: AStockSnapshot,
        technical: AStockTechnicalView,
        sentiment: AStockSentimentView,
    ) -> list[str]:
        risks: list[str] = []
        if technical.average_amplitude_pct is not None and technical.average_amplitude_pct > 5:
            risks.append("近20日平均振幅偏高，短线波动风险较大。")
        if technical.range_position_pct is not None and technical.range_position_pct > 85:
            risks.append("价格接近近20日高位，追高风险上升。")
        if technical.change_20d_pct is not None and technical.change_20d_pct < -10:
            risks.append("近20日跌幅较大，趋势修复前需控制仓位。")
        if sentiment.negative_hits:
            risks.append("消息/公告中出现负面关键词，需要人工复核具体内容。")
        failed_sources = [item for item in snapshot.source_status if not item.ok]
        if failed_sources:
            risks.append("部分数据源不可用，分析完整性下降。")
        return risks

    def _build_summary(
        self,
        snapshot: AStockSnapshot,
        name: str | None,
        bias: AnalysisBias,
        confidence: float,
        technical: AStockTechnicalView,
        sentiment: AStockSentimentView,
    ) -> str:
        label = f"{name or snapshot.symbol}"
        return (
            f"{label} 当前综合倾向为 {bias}，置信度约 {confidence:.0%}。"
            f"技术面为 {technical.trend}，消息面为 {sentiment.bias}。"
            "该结果适合作为策略 Agent 的输入，不应单独作为交易指令。"
        )

    def _resolve_name(self, snapshot: AStockSnapshot) -> str | None:
        if snapshot.quote is not None and snapshot.quote.name:
            return snapshot.quote.name
        if snapshot.company_profile is not None and snapshot.company_profile.name:
            return snapshot.company_profile.name
        return None

    def _fmt(self, value: float | None) -> str:
        return "--" if value is None else f"{value:.2f}"

    def _fmt_pct(self, value: float | None) -> str:
        return "--" if value is None else f"{value:.2f}%"


class AStockAnalysisService:
    """Facade combining data fetching and analysis."""

    def __init__(
        self,
        data_service: AStockDataService | None = None,
        analyzer: AStockAnalyzer | None = None,
    ) -> None:
        self.data_service = data_service or AStockDataService()
        self.analyzer = analyzer or AStockAnalyzer()

    async def analyze_symbol(
        self,
        symbol: str,
        *,
        kline_limit: int = 120,
        news_limit: int = 10,
        announcement_limit: int = 10,
    ) -> AStockAnalysisReport:
        stock = normalize_symbol(symbol)
        snapshot = await self.data_service.get_full_snapshot(
            stock.canonical,
            kline_limit=kline_limit,
            news_limit=news_limit,
            announcement_limit=announcement_limit,
        )
        return self.analyzer.analyze(snapshot)

    def to_markdown(self, report: AStockAnalysisReport) -> str:
        return self.analyzer.to_markdown(report)


def extract_astock_symbol(text: str) -> str | None:
    patterns = (
        r"\b(?:SH|SZ|BJ)\d{6}\b",
        r"\b\d{6}\.(?:SH|SZ|BJ)\b",
        r"\b(?:SSE|SZSE|BSE):\d{6}\b",
        r"(?<!\d)\d{6}(?!\d)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def _moving_average(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[-window:])


def _period_change(values: list[float], sessions: int) -> float | None:
    if len(values) <= sessions:
        return None
    base = values[-sessions - 1]
    if base == 0:
        return None
    return (values[-1] - base) / base * 100


def _range_position(latest: float, low: float | None, high: float | None) -> float | None:
    if low is None or high is None or high == low:
        return None
    return (latest - low) / (high - low) * 100


def _keyword_hits(texts: list[str], keywords: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for text in texts:
        for keyword in keywords:
            if keyword in text and keyword not in hits:
                hits.append(keyword)
    return hits


def _bias_score(bias: AnalysisBias) -> int:
    if bias == "bullish":
        return 1
    if bias == "bearish":
        return -1
    return 0
