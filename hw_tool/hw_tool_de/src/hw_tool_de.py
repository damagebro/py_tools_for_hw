#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


GROUP_ROOT = Path(__file__).resolve().parents[1]
HUB_SRC = GROUP_ROOT.parent / "src"

if "HW_TOOL_HOME" not in os.environ:
    os.environ["HW_TOOL_HOME"] = str(GROUP_ROOT)
sys.path.append(str(HUB_SRC))

from hw_tool import main


if __name__ == "__main__":
    raise SystemExit(main())
