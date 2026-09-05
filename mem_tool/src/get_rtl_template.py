from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile
from typing import Sequence


MEM_TOOL_ROOT = Path(__file__).resolve().parents[1]
SHELL_PATH = MEM_TOOL_ROOT / "rtl" / "shell"
OUTPUT_PATH = Path(__file__).resolve().with_name("rtl_template.py")


def _raw_string(content: str, source: Path) -> str:
    if '"""' in content:
        raise ValueError(f'{source}: RTL template cannot contain \'"""\'')
    if content.endswith("\\"):
        raise ValueError(f"{source}: RTL template cannot end with a backslash")
    return f'r"""{content}"""'


def render_rtl_template(shell_path: Path = SHELL_PATH) -> str:
    source_files = sorted(shell_path.glob("*.sv"), key=lambda path: path.name)
    if not source_files:
        raise FileNotFoundError(f"no SystemVerilog templates found in {shell_path}")

    lines = [
        '"""Generated RTL strings. Run get_rtl_template.py after editing rtl/shell."""',
        "",
        "# This file is generated. Do not edit it directly.",
        "RTL_TEMPLATES: dict[str, str] = {",
    ]
    for source in source_files:
        content = source.read_text(encoding="utf-8")
        lines.append(f'    "{source.name}": {_raw_string(content, source)},')
    lines.extend(["}", ""])
    return "\n".join(lines)


def atomic_write(path: Path, content: str) -> bool:
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return True


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronize rtl/shell/*.sv into rtl_template.py."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="return an error when rtl_template.py is not synchronized",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    generated = render_rtl_template()
    if args.check:
        current = (
            OUTPUT_PATH.read_text(encoding="utf-8")
            if OUTPUT_PATH.is_file()
            else None
        )
        if current != generated:
            print(
                "rtl_template.py is stale; run "
                "python src/get_rtl_template.py"
            )
            return 1
        print("rtl_template.py is synchronized")
        return 0

    changed = atomic_write(OUTPUT_PATH, generated)
    action = "updated" if changed else "already synchronized"
    print(f"{OUTPUT_PATH.name}: {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
