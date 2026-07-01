"""A-share decision guardrails for strategy composers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger

from valuecell.agents.common.trading.constants import FEATURE_GROUP_BY_KEY
from valuecell.agents.common.trading.models import (
    ComposeContext,
    TradeDecisionAction,
    TradeDecisionItem,
    TradePlanProposal,
    UserRequest,
)
from valuecell.agents.common.trading.utils import extract_price_map

ASTOCK_ANALYSIS_GROUP = "astock_analysis"
ASTOCK_EXCHANGE_IDS = {"astock", "a-share", "ashare", "cn-stock"}
DEFAULT_MIN_OPEN_CONFIDENCE = 0.60
DEFAULT_MAX_POSITION_PCT = 0.30
CHINA_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class AStockGuardrailResult:
    plan: TradePlanProposal
    reasons: list[str]


class AStockDecisionGuardrails:
    """Post-LLM safety layer for A-share trade proposals.

    Rules are intentionally conservative:
    - A-shares are spot-only and long-only.
    - New exposure is blocked outside mainland China trading sessions.
    - Low-confidence or risky analysis blocks new opens but still allows closing.
    - Per-symbol exposure is capped as a percentage of portfolio equity.
    """

    def __init__(
        self,
        request: UserRequest,
        *,
        min_open_confidence: float = DEFAULT_MIN_OPEN_CONFIDENCE,
        max_position_pct: float = DEFAULT_MAX_POSITION_PCT,
    ) -> None:
        self._request = request
        self._min_open_confidence = min_open_confidence
        self._max_position_pct = max_position_pct

    def applies(self, context: ComposeContext) -> bool:
        exchange_id = (self._request.exchange_config.exchange_id or "").lower()
        if exchange_id in ASTOCK_EXCHANGE_IDS:
            return True
        return any(
            (feature.meta or {}).get(FEATURE_GROUP_BY_KEY) == ASTOCK_ANALYSIS_GROUP
            for feature in context.features
        )

    def apply(self, context: ComposeContext, plan: TradePlanProposal) -> AStockGuardrailResult:
        if not self.applies(context):
            return AStockGuardrailResult(plan=plan, reasons=[])

        reasons: list[str] = []
        analysis_by_symbol = self._analysis_by_symbol(context)
        price_map = extract_price_map(context.features)
        equity = self._portfolio_equity(context)
        market_open = self._is_china_a_share_trading_session()
        filtered_items: list[TradeDecisionItem] = []

        for item in plan.items:
            symbol = item.instrument.symbol
            action = item.action
            if action in (TradeDecisionAction.OPEN_SHORT, TradeDecisionAction.CLOSE_SHORT):
                reasons.append(f"{symbol}: blocked short-side action {action.value}")
                continue

            if action == TradeDecisionAction.NOOP:
                continue

            normalized = item
            if normalized.leverage is not None and normalized.leverage > 1:
                normalized = normalized.model_copy(update={"leverage": 1.0})
                reasons.append(f"{symbol}: leverage clamped to 1.0 for A-share spot")

            if action == TradeDecisionAction.OPEN_LONG:
                analysis = analysis_by_symbol.get(symbol) or analysis_by_symbol.get(symbol.upper())
                confidence = self._analysis_confidence(analysis)
                risk_flags = self._risk_flags(analysis)
                if not market_open:
                    reasons.append(f"{symbol}: blocked open_long outside A-share trading hours")
                    continue
                if confidence is not None and confidence < self._min_open_confidence:
                    reasons.append(
                        f"{symbol}: blocked open_long because analysis confidence "
                        f"{confidence:.2f} < {self._min_open_confidence:.2f}"
                    )
                    continue
                if risk_flags:
                    reasons.append(f"{symbol}: blocked open_long because risk flags exist")
                    continue
                normalized = self._clamp_position_size(
                    context=context,
                    item=normalized,
                    price_map=price_map,
                    equity=equity,
                    reasons=reasons,
                )
                if normalized.target_qty <= 0:
                    reasons.append(f"{symbol}: blocked open_long after position cap")
                    continue

            filtered_items.append(normalized)

        rationale = plan.rationale or ""
        if reasons:
            rationale = (rationale + "\n\nA-share guardrails: " + "; ".join(reasons)).strip()
            logger.info("A-share guardrails applied: {}", "; ".join(reasons))

        guarded_plan = plan.model_copy(update={"items": filtered_items, "rationale": rationale})
        return AStockGuardrailResult(plan=guarded_plan, reasons=reasons)

    def _clamp_position_size(
        self,
        *,
        context: ComposeContext,
        item: TradeDecisionItem,
        price_map: dict[str, float],
        equity: float,
        reasons: list[str],
    ) -> TradeDecisionItem:
        symbol = item.instrument.symbol
        price = price_map.get(symbol)
        if price is None or price <= 0 or equity <= 0:
            return item
        current_qty = float(context.portfolio.positions.get(symbol).quantity) if symbol in context.portfolio.positions else 0.0
        max_abs_qty = equity * self._max_position_pct / price
        remaining_qty = max(0.0, max_abs_qty - max(0.0, current_qty))
        if item.target_qty > remaining_qty:
            reasons.append(
                f"{symbol}: target_qty clamped from {item.target_qty:.6f} "
                f"to {remaining_qty:.6f} by {self._max_position_pct:.0%} position cap"
            )
            return item.model_copy(update={"target_qty": remaining_qty})
        return item

    def _analysis_by_symbol(self, context: ComposeContext) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for feature in context.features:
            if (feature.meta or {}).get(FEATURE_GROUP_BY_KEY) != ASTOCK_ANALYSIS_GROUP:
                continue
            result[feature.instrument.symbol] = dict(feature.values or {})
        return result

    def _analysis_confidence(self, analysis: dict[str, Any] | None) -> float | None:
        if not analysis:
            return None
        value = analysis.get("analysis.confidence")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _risk_flags(self, analysis: dict[str, Any] | None) -> list[str]:
        if not analysis:
            return []
        value = analysis.get("risk.flags")
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value]
        return []

    def _portfolio_equity(self, context: ComposeContext) -> float:
        if context.portfolio.total_value is not None:
            return float(context.portfolio.total_value or 0.0)
        return float(context.portfolio.account_balance or 0.0)

    def _is_china_a_share_trading_session(self) -> bool:
        now = datetime.now(CHINA_TZ)
        if now.weekday() >= 5:
            return False
        current = now.time()
        morning = time(9, 30) <= current <= time(11, 30)
        afternoon = time(13, 0) <= current <= time(15, 0)
        return morning or afternoon
