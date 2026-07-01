"""A-share strategy preview service.

This module provides a cheap end-to-end dry run:
A-share data -> AStockAnalysis -> rule proposal -> AStockGuardrails -> final action.
It intentionally does not place orders and does not call an LLM.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from valuecell.agents.common.trading.constants import FEATURE_GROUP_BY_KEY
from valuecell.agents.common.trading.decision.astock_guardrails import (
    AStockDecisionGuardrails,
)
from valuecell.agents.common.trading.features.astock_analysis import (
    AStockAnalysisFeaturesPipeline,
)
from valuecell.agents.common.trading.models import (
    ComposeContext,
    InstrumentRef,
    PortfolioView,
    TradeDecisionAction,
    TradeDecisionItem,
    TradeDigest,
    TradePlanProposal,
    UserRequest,
)
from valuecell.server.services.astock.analysis import AStockAnalysisReport
from valuecell.utils.ts import get_current_timestamp_ms

PreviewAction = Literal["buy", "sell", "hold"]


class AStockStrategyPreviewRequest(BaseModel):
    symbol: str
    initial_capital: float = Field(default=100000.0, gt=0)
    current_position_qty: float = Field(default=0.0, ge=0)
    max_position_pct: float = Field(default=0.30, gt=0, le=1)
    open_position_pct: float = Field(default=0.10, gt=0, le=1)
    min_open_confidence: float = Field(default=0.60, ge=0, le=1)
    kline_limit: int = Field(default=120, ge=20, le=1000)
    news_limit: int = Field(default=10, ge=0, le=50)
    announcement_limit: int = Field(default=10, ge=0, le=50)


class AStockStrategyPreviewResponse(BaseModel):
    symbol: str
    action: PreviewAction
    proposed_action: str
    final_items: list[dict]
    blocked_reasons: list[str] = Field(default_factory=list)
    rationale: str
    analysis: AStockAnalysisReport


class AStockStrategyPreviewService:
    """Dry-run A-share strategy decision service."""

    async def preview(
        self, request: AStockStrategyPreviewRequest
    ) -> AStockStrategyPreviewResponse:
        user_request = self._build_user_request(request)
        pipeline = AStockAnalysisFeaturesPipeline(
            request=user_request,
            kline_limit=request.kline_limit,
            news_limit=request.news_limit,
            announcement_limit=request.announcement_limit,
        )
        features_result = await pipeline.build()
        report = self._extract_report_from_features(request.symbol, features_result.features)
        if report is None:
            # Fallback: the pipeline already normalizes symbols, but keep a clear failure mode.
            raise ValueError(f"Unable to build A-share analysis for {request.symbol}")

        context = self._build_context(
            user_request=user_request,
            request=request,
            features=features_result.features,
            symbol=report.symbol,
            latest_price=report.technical.latest_close,
        )
        proposal = self._build_rule_proposal(request, report)
        guarded = AStockDecisionGuardrails(
            user_request,
            min_open_confidence=request.min_open_confidence,
            max_position_pct=request.max_position_pct,
        ).apply(context, proposal)
        action = self._final_action(guarded.plan)
        return AStockStrategyPreviewResponse(
            symbol=report.symbol,
            action=action,
            proposed_action=self._proposal_action(proposal),
            final_items=[item.model_dump(mode="json") for item in guarded.plan.items],
            blocked_reasons=guarded.reasons,
            rationale=guarded.plan.rationale or "",
            analysis=report,
        )

    def _build_user_request(self, request: AStockStrategyPreviewRequest) -> UserRequest:
        return UserRequest.model_validate(
            {
                "llm_model_config": {
                    "provider": "siliconflow",
                    "model_id": "dry-run",
                    "api_key": "dry-run",
                },
                "exchange_config": {
                    "exchange_id": "astock",
                    "trading_mode": "virtual",
                    "market_type": "spot",
                },
                "trading_config": {
                    "symbols": [request.symbol],
                    "initial_capital": request.initial_capital,
                    "initial_free_cash": request.initial_capital,
                    "max_leverage": 1,
                    "max_positions": 1,
                    "cap_factor": request.max_position_pct,
                    "custom_prompt": "A-share dry-run preview; no live order execution.",
                },
            }
        )

    def _extract_report_from_features(self, symbol: str, features) -> AStockAnalysisReport | None:
        for feature in features:
            if (feature.meta or {}).get(FEATURE_GROUP_BY_KEY) != "astock_analysis":
                continue
            values = feature.values
            # Re-run the report through the feature values is lossy, so fetch the report
            # from the feature metadata is not possible. Instead construct the minimum
            # response later from a direct analysis call would duplicate IO. We store the
            # report JSON in the feature in a backwards-compatible optional field.
            raw = values.get("analysis.report_json")
            if isinstance(raw, str):
                return AStockAnalysisReport.model_validate(json.loads(raw))
        return None

    def _build_context(
        self,
        *,
        user_request: UserRequest,
        request: AStockStrategyPreviewRequest,
        features,
        symbol: str,
        latest_price: float | None,
    ) -> ComposeContext:
        now = get_current_timestamp_ms()
        positions = {}
        if request.current_position_qty > 0:
            from valuecell.agents.common.trading.models import PositionSnapshot, TradeType

            positions[symbol] = PositionSnapshot(
                instrument=InstrumentRef(symbol=symbol, exchange_id="astock"),
                quantity=request.current_position_qty,
                avg_price=latest_price,
                mark_price=latest_price,
                trade_type=TradeType.LONG,
            )
        return ComposeContext(
            ts=now,
            compose_id="astock-preview",
            strategy_id="astock-preview",
            features=features,
            portfolio=PortfolioView(
                ts=now,
                account_balance=request.initial_capital,
                free_cash=request.initial_capital,
                total_value=request.initial_capital,
                positions=positions,
                constraints=None,
            ),
            digest=TradeDigest(ts=now, by_instrument={}),
        )

    def _build_rule_proposal(
        self,
        request: AStockStrategyPreviewRequest,
        report: AStockAnalysisReport,
    ) -> TradePlanProposal:
        instrument = InstrumentRef(symbol=report.symbol, exchange_id="astock")
        price = report.technical.latest_close or 0
        qty = 0.0
        if price > 0:
            qty = request.initial_capital * request.open_position_pct / price

        if report.bias == "bullish" and report.confidence >= request.min_open_confidence:
            item = TradeDecisionItem(
                instrument=instrument,
                action=TradeDecisionAction.OPEN_LONG,
                target_qty=qty,
                leverage=1.0,
                confidence=report.confidence,
                rationale="Rule proposal: bullish A-share analysis with sufficient confidence.",
            )
            items = [item]
        elif report.bias == "bearish" and request.current_position_qty > 0:
            item = TradeDecisionItem(
                instrument=instrument,
                action=TradeDecisionAction.CLOSE_LONG,
                target_qty=request.current_position_qty,
                leverage=1.0,
                confidence=report.confidence,
                rationale="Rule proposal: bearish A-share analysis, close existing long position.",
            )
            items = [item]
        else:
            items = []

        return TradePlanProposal(
            items=items,
            rationale=(
                f"Rule proposal from AStockAnalysis: bias={report.bias}, "
                f"confidence={report.confidence:.2f}."
            ),
        )

    def _proposal_action(self, proposal: TradePlanProposal) -> str:
        if not proposal.items:
            return "noop"
        return proposal.items[0].action.value

    def _final_action(self, plan: TradePlanProposal) -> PreviewAction:
        if not plan.items:
            return "hold"
        action = plan.items[0].action
        if action == TradeDecisionAction.OPEN_LONG:
            return "buy"
        if action == TradeDecisionAction.CLOSE_LONG:
            return "sell"
        return "hold"
