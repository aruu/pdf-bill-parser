"""Shared pytest configuration.

The application modules under `src/` import each other using bare module
names (e.g. `from config import get_config`, `import google_sheets as gs`),
which means `src/` must be on `sys.path` for those imports to resolve. This
mirrors how the app is actually run (from within `src/`).
"""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))