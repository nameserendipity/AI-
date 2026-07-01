"""Server-side strategy auto-resume logic.

This module scans persisted strategies with status 'running' on process
startup and dispatches them through the existing AgentOrchestrator using
their stored configuration. The core orchestrator remains unaware of
auto-resume concerns per design (separation of coordination vs runtime ops).

Resume Semantics:
 - Strategies whose status == 'running' (previous session crashed) are resumed.
 - Strategies whose status == 'stopped' with metadata.stop_reason == 'cancelled'
     (gracefully cancelled but intended to auto-resume) are also resumed.
 - Each strategy's original config dict is parsed into a UserRequest.
 - The stored strategy_id is injected into TradingConfig.strategy_id so the
   underlying runtime reuses portfolio state (idempotent initial snapshot).
 - Streaming responses are consumed and discarded (fire-and-forget). External
   observers can implement their own hooks if needed.

Failures during individual strategy resume are logged and skipped without
impacting other candidates.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

from loguru import logger

from valuecell.agents.common.trading.models import (
    StopReason,
    StrategyStatus,
    StrategyStatusContent,
    UserRequest,
)
from valuecell.core.coordinate.orchestrator import AgentOrchestrator
from valuecell.core.types import CommonResponseEvent, UserInput, UserInputMetadata
from valuecell.server.db.models.strategy import Strategy
from valuecell.server.db.repositories.strategy_repository import get_strategy_repository
from valuecell.server.services import strategy_persistence
from valuecell.utils.uuid import generate_conversation_id

_AUTORESUME_STARTED = False


async def auto_resume_strategies(
    orchestrator: AgentOrchestrator,
    max_strategies: Optional[int] = None,
) -> None:
    """Dispatch background resume tasks for persisted running strategies.

    Args:
        orchestrator: Existing AgentOrchestrator instance.
        max_strategies: Optional limit to number of strategies resumed.
    """
    global _AUTORESUME_STARTED
    if _AUTORESUME_STARTED:
        return
    _AUTORESUME_STARTED = True

    try:
        repo = get_strategy_repository()
        rows = repo.list_strategies_by_status(
            [StrategyStatus.RUNNING.value, StrategyStatus.STOPPED.value],
            limit=max_strategies,
        )
        candidates = [s for s in rows if _should_resume(s)]
        if not candidates:
            logger.info("Auto-resume: no eligible strategies found")
            return
        logger.info("Auto-resume: found {} eligible strategies", len(candidates))
        # Create tasks for each resume and keep them running. We await the
        # gathered tasks so that when this coroutine is run with
        # `asyncio.run(...)` (background thread) the loop stays alive until
        # the resumed strategies finish. When scheduled on an already-running
        # loop, this will run as background tasks concurrently as well.
        tasks = [asyncio.create_task(_resume_one(orchestrator, s)) for s in candidates]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Auto-resume scan failed")


def _is_missing_secret(value: Any) -> bool:
    """Return True when a persisted credential value needs environment fallback."""
    return value is None or (isinstance(value, str) and value.strip() == "")


def _first_env_value(names: list[str]) -> Optional[str]:
    """Return the first non-empty environment variable value from names."""
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def _exchange_env_prefix(exchange_id: Optional[str]) -> Optional[str]:
    """Return the conventional env prefix for a supported exchange."""
    if not exchange_id:
        return None
    normalized = exchange_id.strip().upper().replace("-", "_")
    return normalized or None


def backfill_exchange_credentials(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Backfill missing live-trading exchange credentials from environment.

    Strategy configs intentionally omit sensitive credentials when persisted.
    Manual restart and auto-resume therefore need to reconstruct the runtime
    request from the current process environment. Existing config values always
    win; environment variables are only used for missing fields.
    """
    config = dict(config_dict or {})
    exchange_config_raw = config.get("exchange_config")
    if not isinstance(exchange_config_raw, dict):
        return config

    exchange_config = dict(exchange_config_raw)
    trading_mode = str(exchange_config.get("trading_mode") or "").strip().lower()
    if trading_mode.startswith("tradingmode."):
        trading_mode = trading_mode.split(".", 1)[1]
    if trading_mode != "live":
        return config

    exchange_id = exchange_config.get("exchange_id")
    prefix = _exchange_env_prefix(str(exchange_id) if exchange_id is not None else None)
    if not prefix:
        return config

    field_env_names = {
        "api_key": [f"{prefix}_API_KEY", "AUTO_TRADING_API_KEY"],
        "secret_key": [
            f"{prefix}_API_SECRET",
            f"{prefix}_SECRET_KEY",
            "AUTO_TRADING_API_SECRET",
            "AUTO_TRADING_SECRET_KEY",
        ],
        "passphrase": [
            f"{prefix}_API_PASSPHRASE",
            f"{prefix}_PASSPHRASE",
            "AUTO_TRADING_API_PASSPHRASE",
            "AUTO_TRADING_PASSPHRASE",
        ],
        "wallet_address": [f"{prefix}_WALLET_ADDRESS", "AUTO_TRADING_WALLET_ADDRESS"],
        "private_key": [f"{prefix}_PRIVATE_KEY", "AUTO_TRADING_PRIVATE_KEY"],
    }

    patched_fields: list[str] = []
    for field_name, env_names in field_env_names.items():
        if not _is_missing_secret(exchange_config.get(field_name)):
            continue
        env_value = _first_env_value(env_names)
        if env_value is None:
            continue
        exchange_config[field_name] = env_value
        patched_fields.append(field_name)

    if patched_fields:
        logger.info(
            "Strategy resume backfilled exchange credential fields for exchange_id={}: {}",
            exchange_id,
            ", ".join(patched_fields),
        )
        config["exchange_config"] = exchange_config

    return config


async def _resume_one(orchestrator: AgentOrchestrator, strategy_row: Strategy) -> bool:
    strategy_id = strategy_row.strategy_id
    try:
        config_dict = backfill_exchange_credentials(strategy_row.config or {})
        metadata = strategy_row.strategy_metadata or {}
        agent_name = metadata.get("agent_name")

        # Parse request; tolerate partial configs
        request = UserRequest.model_validate(config_dict)
        if request.trading_config.strategy_id is None and strategy_id:
            request.trading_config.strategy_id = strategy_id

        user_input = UserInput(
            query=request.model_dump_json(),
            target_agent_name=agent_name,
            meta=UserInputMetadata(
                user_id=strategy_row.user_id,
                conversation_id=generate_conversation_id(),
            ),
        )

        async for chunk in orchestrator.process_user_input(user_input):
            logger.debug("Auto-resume chunk for strategy_id={}: {}", strategy_id, chunk)
            if chunk.event == CommonResponseEvent.COMPONENT_GENERATOR:
                logger.info(
                    "Auto-resume dispatched strategy_id={} agent={}",
                    strategy_id,
                    agent_name,
                )
                status_content = StrategyStatusContent.model_validate_json(
                    chunk.data.payload.content
                )
                strategy_persistence.set_strategy_status(
                    strategy_id, status_content.status.value
                )
                return status_content.status == StrategyStatus.RUNNING

        logger.warning(
            "Auto-resume did not receive a status event for strategy_id={}",
            strategy_id or "<unknown>",
        )
        return False

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(
            "Auto-resume failed for strategy_id={}", strategy_id or "<unknown>"
        )
        return False


async def resume_strategy(
    orchestrator: AgentOrchestrator,
    strategy_row: Strategy,
) -> bool:
    """Resume one persisted strategy immediately using its stored config."""
    return await _resume_one(orchestrator, strategy_row)


def _should_resume(strategy_row: Strategy) -> bool:
    """Return True if strategy should be auto-resumed based on status/metadata."""
    status_raw = strategy_row.status or ""
    metadata = strategy_row.strategy_metadata or {}
    try:
        status_enum = StrategyStatus(status_raw)
    except Exception:
        # Unknown/invalid status - skip
        return False

    if status_enum == StrategyStatus.RUNNING:
        return True

    if (
        status_enum == StrategyStatus.STOPPED
        and metadata.get("stop_reason") == StopReason.CANCELLED.value
    ):
        return True

    return False
