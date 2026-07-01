"""A-share stock symbol normalization utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass


class AStockSymbolError(ValueError):
    """Raised when an A-share symbol cannot be normalized."""


@dataclass(frozen=True)
class AStockSymbol:
    """Canonical A-share symbol representation.

    The canonical external format is `<code>.<exchange>`, for example
    `600519.SH`, `300750.SZ`, or `833171.BJ`.
    """

    code: str
    exchange: str

    @property
    def canonical(self) -> str:
        return f"{self.code}.{self.exchange}"

    @property
    def akshare_code(self) -> str:
        return self.code

    @property
    def internal_ticker(self) -> str:
        exchange_map = {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}
        return f"{exchange_map[self.exchange]}:{self.code}"


def infer_exchange(code: str) -> str:
    """Infer A-share exchange from a 6-digit security code."""
    if not re.fullmatch(r"\d{6}", code):
        raise AStockSymbolError(f"Invalid A-share code: {code}")

    if code.startswith(("600", "601", "603", "605", "688", "689", "900")):
        return "SH"
    if code.startswith(("000", "001", "002", "003", "200", "300", "301")):
        return "SZ"
    if code.startswith(("4", "8", "9")):
        return "BJ"
    raise AStockSymbolError(f"Cannot infer exchange for A-share code: {code}")


def normalize_symbol(symbol: str) -> AStockSymbol:
    """Normalize common A-share formats into `AStockSymbol`.

    Supported inputs include:
    - `300750`
    - `300750.SZ`, `600519.SH`, `833171.BJ`
    - `SZSE:300750`, `SSE:600519`, `BSE:833171`
    - `sz300750`, `sh600519`, `bj833171`
    """
    raw = str(symbol or "").strip().upper()
    if not raw:
        raise AStockSymbolError("A-share symbol cannot be empty")

    raw = raw.replace(" ", "")

    internal_match = re.fullmatch(r"(SSE|SZSE|BSE):(\d{6})", raw)
    if internal_match:
        exchange = {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}[internal_match.group(1)]
        return AStockSymbol(code=internal_match.group(2), exchange=exchange)

    prefixed_match = re.fullmatch(r"(SH|SZ|BJ)(\d{6})", raw)
    if prefixed_match:
        return AStockSymbol(code=prefixed_match.group(2), exchange=prefixed_match.group(1))

    dotted_match = re.fullmatch(r"(\d{6})\.(SH|SZ|BJ|SS)", raw)
    if dotted_match:
        exchange = "SH" if dotted_match.group(2) == "SS" else dotted_match.group(2)
        return AStockSymbol(code=dotted_match.group(1), exchange=exchange)

    if re.fullmatch(r"\d{6}", raw):
        return AStockSymbol(code=raw, exchange=infer_exchange(raw))

    raise AStockSymbolError(f"Unsupported A-share symbol format: {symbol}")
