"""Run scheduled A-share market-memory analysis.

Examples:
    uv run python scripts/astock_memory_runner.py --once
    uv run python scripts/astock_memory_runner.py --interval-minutes 60
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from loguru import logger

from valuecell.server.db import init_database
from valuecell.server.services.astock.memory import (
    AStockMemoryService,
    MemoryRunnerConfig,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scheduled A-share market-memory analysis runner"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one cycle and exit instead of looping forever.",
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=int(os.getenv("ASTOCK_MEMORY_INTERVAL_MINUTES", "60")),
        help="Minutes between cycles. Default: 60.",
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=int(os.getenv("ASTOCK_MEMORY_HISTORY_LIMIT", "5")),
        help="Number of recent memory items to include per symbol. Default: 5.",
    )
    parser.add_argument(
        "--watchlist-user",
        default=os.getenv("ASTOCK_MEMORY_WATCHLIST_USER", "default_user"),
        help="Watchlist user id. Default: default_user.",
    )
    parser.add_argument(
        "--market",
        default=os.getenv("ASTOCK_MEMORY_MARKET", "astock"),
        help="Market analyzer to run. Only 'astock' is implemented in v1.",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=float(os.getenv("ASTOCK_MEMORY_INITIAL_CAPITAL", "100000")),
        help="Virtual initial capital for A-share preview sizing.",
    )
    parser.add_argument(
        "--model-provider",
        default=os.getenv("ASTOCK_MEMORY_MODEL_PROVIDER", "deepseek"),
        help="Model provider used for memory synthesis. Default: deepseek.",
    )
    parser.add_argument(
        "--model-id",
        default=os.getenv("ASTOCK_MEMORY_MODEL_ID") or None,
        help="Optional model id override.",
    )
    return parser.parse_args()


async def run_cycle(config: MemoryRunnerConfig) -> str:
    service = AStockMemoryService(config=config)
    return await service.run_once()


async def main_async() -> None:
    args = parse_args()
    if args.market != "astock":
        raise SystemExit("Only --market astock is implemented in v1.")

    config = MemoryRunnerConfig(
        interval_minutes=args.interval_minutes,
        history_limit=args.history_limit,
        watchlist_user=args.watchlist_user,
        market=args.market,
        initial_capital=args.initial_capital,
        model_provider=args.model_provider,
        model_id=args.model_id,
    )

    logger.info("Initializing database before A-share memory runner starts...")
    if not init_database(force=False):
        raise SystemExit("Database initialization failed.")

    logger.info(
        "A-share memory runner started: interval={} minutes, user={}, provider={}, model={}",
        config.interval_minutes,
        config.watchlist_user,
        config.model_provider,
        config.model_id or "provider-default",
    )

    while True:
        try:
            run_id = await run_cycle(config)
            logger.info("A-share memory cycle completed: {}", run_id)
        except Exception:
            logger.exception("A-share memory cycle failed")

        if args.once:
            return

        sleep_seconds = config.interval_minutes * 60
        logger.info("Sleeping {} seconds before next cycle...", sleep_seconds)
        await asyncio.sleep(sleep_seconds)


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("A-share memory runner stopped by user")


if __name__ == "__main__":
    # Keep relative paths predictable when invoked from other directories.
    python_root = Path(__file__).resolve().parents[1]
    os.chdir(python_root)
    main()

