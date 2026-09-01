#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SNIPPET_SCRIPT = ROOT / "py_rtl_snippet" / "src" / "py_rtl_snippet.py"
SNIPPET_INPUT = ROOT / "py_rtl_snippet" / "input" / "rtl_snippets.md"
SNIPPET_OUTPUT = Path(__file__).resolve().parents[1] / "resources" / "systemverilog.code-snippets"


def main() -> int:
    SNIPPET_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-B", str(SNIPPET_SCRIPT), "-i", str(SNIPPET_INPUT), "-o", str(SNIPPET_OUTPUT)],
        check=False,
    )
    if result.returncode != 0:
        return result.returncode
    print(f"synced {SNIPPET_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
