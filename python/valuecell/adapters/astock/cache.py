"""Simple JSON cache for A-share data snapshots."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from valuecell.utils.env import get_system_env_dir


def get_astock_cache_dir() -> Path:
    path = Path(get_system_env_dir()) / "astock" / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_name(key: str) -> str:
    return key.replace(":", "_").replace("/", "_").replace("\\", "_")


def write_json_cache(namespace: str, key: str, data: dict[str, Any]) -> Path:
    directory = get_astock_cache_dir() / namespace
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{_safe_name(key)}.json"
    payload = {
        "cached_at": datetime.utcnow().isoformat(),
        "data": data,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_json_cache(
    namespace: str,
    key: str,
    *,
    max_age_seconds: int | None = None,
) -> dict[str, Any] | None:
    path = get_astock_cache_dir() / namespace / f"{_safe_name(key)}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        cached_at_raw = payload.get("cached_at")
        if max_age_seconds is not None and cached_at_raw:
            cached_at = datetime.fromisoformat(cached_at_raw)
            if datetime.utcnow() - cached_at > timedelta(seconds=max_age_seconds):
                return None
        data = payload.get("data")
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read A-stock cache {}:{}: {}", namespace, key, exc)
        return None
