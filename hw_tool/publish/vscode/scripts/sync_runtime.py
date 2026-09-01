#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXTENSION_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = ROOT / "hw_tool" / "publish"
DE_SOURCE_ROOT = ROOT / "hw_tool" / "hw_tool_de" / "src"
RUNTIME_ROOT = EXTENSION_ROOT / "runtime"

sys.path.insert(0, str(BUILD_ROOT))
from build_release import build_release, remove_readonly

sys.path.insert(0, str(DE_SOURCE_ROOT))
from tool_registry import REPOSITORY_MAP, TOOL_SPECS


def extension_version() -> str:
    package = json.loads((EXTENSION_ROOT / "package.json").read_text(encoding="utf-8"))
    version = package.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("package.json must define a non-empty version")
    return version


def write_tool_document_index(runtime_tool_root: Path) -> None:
    documents = []
    for tool in TOOL_SPECS:
        if not tool.readme or not tool.repository_name:
            continue
        repository = REPOSITORY_MAP.get(tool.repository_name)
        if repository is None:
            raise ValueError(
                f"tool '{tool.name}' references unknown repository "
                f"'{tool.repository_name}'"
            )
        relative_path = Path("repository") / repository.name / tool.readme
        if not (runtime_tool_root / relative_path).is_file():
            raise FileNotFoundError(
                f"README for '{tool.name}' is missing from runtime: {relative_path}"
            )
        documents.append({
            "name": tool.name,
            "description": tool.description,
            "readme": relative_path.as_posix(),
        })
    (runtime_tool_root / "tool_docs.json").write_text(
        json.dumps({"tools": documents}, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    version = extension_version()
    with tempfile.TemporaryDirectory(prefix="dmg_hw_tool_runtime_") as temporary_directory:
        temporary_root = Path(temporary_directory)
        tool_root, _ = build_release(version, temporary_root, create_archive=False)
        if RUNTIME_ROOT.exists():
            shutil.rmtree(RUNTIME_ROOT, onerror=remove_readonly)
        RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tool_root), str(RUNTIME_ROOT / "hw_tool"))
        write_tool_document_index(RUNTIME_ROOT / "hw_tool")

    print(f"synced {RUNTIME_ROOT / 'hw_tool'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
