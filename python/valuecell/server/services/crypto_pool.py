"""Dynamic crypto candidate pool scanner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os

from loguru import logger

from valuecell.agents.common.trading.utils import get_exchange_cls
from valuecell.server.db.repositories.crypto_pool_repository import (
    get_crypto_pool_repository,
)


@dataclass
class CryptoPoolScannerConfig:
    exchange_id: str = "okx"
    market_type: str = "swap"
    quote_currency: str = "USDT"
    top_n: int = 20
    min_quote_volume: float = 5_000_000.0
    max_spread_pct: float = 0.5


class CryptoPoolScanner:
    """Scan exchange tickers and persist a ranked dynamic candidate pool."""

    def __init__(self, config: CryptoPoolScannerConfig | None = None):
        self.config = config or CryptoPoolScannerConfig()

    async def scan_once(self) -> list[dict]:
        exchange_cls = get_exchange_cls(self.config.exchange_id)
        exchange_options = {
            "newUpdates": False,
            "options": {"defaultType": self.config.market_type},
        }
        proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
        if proxy:
            exchange_options["aiohttp_proxy"] = proxy
        exchange = exchange_cls(exchange_options)
        try:
            tickers = await exchange.fetch_tickers()
        finally:
            try:
                await exchange.close()
            except Exception:
                logger.exception("Failed to close crypto pool exchange connection")

        candidates: list[dict] = []
        for raw_symbol, ticker in (tickers or {}).items():
            candidate = self._build_candidate(raw_symbol, ticker)
            if candidate is not None:
                candidates.append(candidate)

        candidates.sort(
            key=lambda item: (float(item["score"]), float(item.get("quote_volume") or 0)),
            reverse=True,
        )
        selected = candidates[: self.config.top_n]
        scanned_at = datetime.now(timezone.utc)
        get_crypto_pool_repository().replace_candidates(
            exchange_id=self.config.exchange_id,
            market_type=self.config.market_type,
            candidates=selected,
            scanned_at=scanned_at,
        )
        logger.info(
            "Crypto pool scan complete: exchange={}, candidates={}, saved={}",
            self.config.exchange_id,
            len(candidates),
            len(selected),
        )
        return selected

    def _build_candidate(self, raw_symbol: str, ticker: dict) -> dict | None:
        parsed = self._parse_symbol(raw_symbol)
        if parsed is None:
            return None
        symbol, normalized_symbol = parsed

        quote_volume = self._as_float(
            ticker.get("quoteVolume")
            or ticker.get("quote_volume")
            or (ticker.get("info") or {}).get("volCcy24h")
            or (ticker.get("info") or {}).get("quoteVolume")
        )
        if quote_volume is None or quote_volume < self.config.min_quote_volume:
            return None

        bid = self._as_float(ticker.get("bid"))
        ask = self._as_float(ticker.get("ask"))
        last = self._as_float(ticker.get("last") or ticker.get("close"))
        spread_pct = None
        if bid and ask and last and last > 0:
            spread_pct = (ask - bid) / last * 100
            if spread_pct > self.config.max_spread_pct:
                return None

        percentage_24h = self._as_float(
            ticker.get("percentage")
            or (ticker.get("info") or {}).get("changeUtc24h")
            or (ticker.get("info") or {}).get("change24h")
        )
        base_volume = self._as_float(ticker.get("baseVolume"))
        score = self._score(
            quote_volume=quote_volume,
            percentage_24h=percentage_24h,
            spread_pct=spread_pct,
        )
        reason_parts = [
            f"24h成交额 {quote_volume:,.0f} {self.config.quote_currency}",
        ]
        if percentage_24h is not None:
            reason_parts.append(f"24h涨跌 {percentage_24h:.2f}%")
        if spread_pct is not None:
            reason_parts.append(f"价差 {spread_pct:.3f}%")

        return {
            "symbol": symbol,
            "normalized_symbol": normalized_symbol,
            "quote_currency": self.config.quote_currency,
            "status": "active",
            "score": score,
            "last_price": last,
            "percentage_24h": percentage_24h,
            "quote_volume": quote_volume,
            "base_volume": base_volume,
            "spread_pct": spread_pct,
            "reason": "；".join(reason_parts),
            "metrics": ticker,
        }

    def _parse_symbol(self, raw_symbol: str) -> tuple[str, str] | None:
        symbol = raw_symbol.upper()
        if not symbol.endswith(f"/{self.config.quote_currency}:{self.config.quote_currency}"):
            return None
        base = symbol.split("/", 1)[0]
        if not base or any(mark in base for mark in ("UP", "DOWN", "BULL", "BEAR")):
            return None
        return f"{base}/{self.config.quote_currency}", symbol

    @staticmethod
    def _as_float(value) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _score(
        *,
        quote_volume: float,
        percentage_24h: float | None,
        spread_pct: float | None,
    ) -> float:
        volume_score = min(60.0, quote_volume / 10_000_000.0)
        momentum_score = min(30.0, abs(percentage_24h or 0.0) * 2.0)
        spread_penalty = min(20.0, (spread_pct or 0.0) * 10.0)
        return max(0.0, volume_score + momentum_score - spread_penalty)
