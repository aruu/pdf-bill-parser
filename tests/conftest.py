"""Shared pytest configuration.

The application modules under ``src/`` (``config``, ``google_sheets``,
``ingest``) import each other using plain top-level imports (e.g.
``import google_sheets as gs``), the same way they would be imported when
``src/`` is the working directory or is otherwise placed on ``sys.path``
(such as when running ``python src/ingest.py`` directly). To mirror that
behavior in tests, we add ``src/`` to ``sys.path`` here.
"""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))