"""Local startup patch for Windows development.

Some Windows environments can hang while importing packages that call
platform.machine()/platform.processor(), because Python may query WMI.  This
project only needs a coarse architecture string during startup, so keep these
calls deterministic.  Set VALUECELL_DISABLE_STARTUP_PATCH=1 to disable.
"""

from __future__ import annotations

import os
import sys

if sys.platform.startswith("win") and os.getenv("VALUECELL_DISABLE_STARTUP_PATCH") != "1":
    try:
        import platform

        platform.machine = lambda: os.getenv("PROCESSOR_ARCHITECTURE", "AMD64") or "AMD64"
        platform.processor = lambda: os.getenv("PROCESSOR_IDENTIFIER", "AMD64") or "AMD64"
    except Exception:
        pass
