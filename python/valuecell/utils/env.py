"""Utilities for resolving system-level .env paths consistently across OSes.

Provides helpers to locate the OS user configuration directory for ValueCell
and to construct the system `.env` file path. This centralizes path logic so
other modules can mirror or write environment variables consistently.
"""

import os
from pathlib import Path


def get_system_env_dir() -> Path:
    """Return the user data/configuration directory for ValueCell.

    Resolution order:
    1. VALUECELL_HOME, when set. Use this to move local data off the system drive.
    2. OS default user configuration directory:
       - macOS: ~/Library/Application Support/ValueCell
       - Linux: ~/.config/valuecell
       - Windows: %APPDATA%\\ValueCell

    This directory stores the system `.env`, SQLite database, LanceDB vector DB,
    and the ResearchAgent `.knowledge` files.
    """
    configured_home = os.getenv("VALUECELL_HOME", "").strip()
    if configured_home:
        return Path(configured_home).expanduser()

    home = Path.home()
    # Windows
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        base = Path(appdata) if appdata else (home / "AppData" / "Roaming")
        return base / "ValueCell"
    # macOS (posix with darwin kernel)
    if sys_platform_is_darwin():
        # Correct macOS Application Support directory path
        return home / "Library" / "Application Support" / "ValueCell"
    # Linux and other Unix-like
    return home / ".config" / "valuecell"


def get_system_env_path() -> Path:
    """Return the full path to the system `.env` file."""
    return get_system_env_dir() / ".env"


def ensure_system_env_dir() -> Path:
    """Ensure the system config directory exists and return it."""
    d = get_system_env_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def sys_platform_is_darwin() -> bool:
    """Detect macOS platform without importing `platform` globally."""
    try:
        import sys

        return sys.platform == "darwin"
    except Exception:
        return False


def agent_debug_mode_enabled() -> bool:
    """Return whether agent debug mode is enabled via environment.

    Checks `AGENT_DEBUG_MODE`.
    """
    flag = os.getenv("AGENT_DEBUG_MODE", "false")
    return str(flag).lower() == "true"

