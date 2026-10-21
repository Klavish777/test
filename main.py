#!/usr/bin/env python3
"""Скрипт запуска Smartphone Repair OS (кроссплатформенный).

    python main.py
    python main.py --data-dir ./data --no-demo
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from repair_os.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
