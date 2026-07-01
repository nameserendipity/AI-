"""Run the dynamic crypto pool scanner."""

from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from valuecell.server.db.init_db import init_database
from valuecell.server.services.crypto_pool import (
    CryptoPoolScanner,
    CryptoPoolScannerConfig,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dynamic crypto pool scanner")
    parser.add_argument("--once", action="store_true", help="Run one scan then exit")
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--exchange-id", default="okx")
    parser.add_argument("--market-type", default="swap")
    parser.add_argument("--quote-currency", default="USDT")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--min-quote-volume", type=float, default=5_000_000.0)
    parser.add_argument("--max-spread-pct", type=float, default=0.5)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    init_database(force=False)
    scanner = CryptoPoolScanner(
        CryptoPoolScannerConfig(
            exchange_id=args.exchange_id,
            market_type=args.market_type,
            quote_currency=args.quote_currency,
            top_n=args.top_n,
            min_quote_volume=args.min_quote_volume,
            max_spread_pct=args.max_spread_pct,
        )
    )
    while True:
        try:
            candidates = await scanner.scan_once()
            logger.info(
                "Top dynamic symbols: {}",
                [item["symbol"] for item in candidates[:5]],
            )
        except Exception:
            logger.exception("Crypto pool scan failed")
        if args.once:
            return
        await asyncio.sleep(max(5, args.interval_seconds))


if __name__ == "__main__":
    asyncio.run(main())
