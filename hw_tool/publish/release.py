#!/usr/bin/env python3
"""Build Windows/Linux sources, modulefile and VSIX from one source revision."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from build_release import (
    OUTPUT_ROOT, load_tool_registry, parse_named_values, populate_release,
    release_source, release_staging,
)
from verify_release import files_under, write_checksums, verify_release


def source_archive(root: Path, version: str) -> Path:
    output = root / f"hw_tool-{version}.zip"
    with ZipFile(output, "x", ZIP_DEFLATED) as archive:
        for directory in (root / "hw_tool", root / "modulefiles"):
            for path in files_under(directory).values():
                info = ZipInfo.from_file(path, path.relative_to(root).as_posix())
                content = path.read_bytes()
                executable = content.startswith(b"#!") and (path.suffix == ".sh" or path.parent.name == "bin")
                info.create_system = 3
                info.external_attr = (0o100755 if executable else 0o100644) << 16
                archive.writestr(info, content, compress_type=ZIP_DEFLATED)
    return output


def write_documents(tool_root: Path) -> None:
    registry = load_tool_registry(tool_root / "hw_tool_de/src/tool_registry.py", "_release_docs")
    documents = []
    for tool in registry.TOOL_SPECS:
        base = Path("repository") / tool.repository_name
        readme, entry = base / tool.readme, base / tool.script
        for path in (readme, entry):
            if not (tool_root / path).is_file():
                raise ValueError(f"missing tool resource: {path}")
        documents.append({"name": tool.name, "description": tool.description,
                          "readme": readme.as_posix(), "entry": entry.as_posix()})
    (tool_root / "tool_docs.json").write_text(
        json.dumps({"tools": documents}, indent=2) + "\n", encoding="utf-8", newline="\n",
    )


def prepare_extension(tool_root: Path, version: str) -> Path:
    extension = tool_root / "publish/vscode"
    package_path = extension / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = version
    package_path.write_text(json.dumps(package, indent=4) + "\n", encoding="utf-8", newline="\n")
    snippets = tool_root / "repository/py_tools_for_hw/py_rtl_snippet"
    subprocess.run([
        sys.executable, "-B", str(snippets / "src/py_rtl_snippet.py"),
        "-i", str(snippets / "input/rtl_snippets.md"),
        "-o", str(extension / "resources/systemverilog.code-snippets"),
    ], check=True)
    return extension


def publish(version: str, output_root: Path = OUTPUT_ROOT, *, official: bool = False,
            repository_refs: dict[str, str] | None = None, shallow: bool = False,
            linux_install_root: str = "/tools/hw_tool") -> Path:
    with release_staging(output_root, version) as (staged, destination):
        with release_source(official, repository_refs or {}, shallow) as source:
            tool_root = populate_release(source, staged, version, official, linux_install_root)
        write_documents(tool_root)
        extension = prepare_extension(tool_root, version)
        write_checksums(tool_root)
        source_archive(staged, version)
        # Stage the editor separately so the shared runtime cannot copy itself recursively.
        with tempfile.TemporaryDirectory(prefix="vsix-", dir=staged.parent) as temporary:
            editor = Path(temporary) / "extension"
            shutil.copytree(extension, editor)
            shutil.copytree(tool_root, editor / "runtime/hw_tool")
            packer = load_tool_registry(Path(__file__).parent / "vscode/scripts/pack_vsix.py", "_release_packer")
            if packer.package_extension(staged / f"dmg-hw-tool-{version}.vsix", editor) != 0:
                raise ValueError("VSIX packaging failed")
        write_checksums(staged)
        verify_release(staged)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--official", action="store_true")
    parser.add_argument("--repo-ref", action="append", default=[], metavar="NAME=REF")
    parser.add_argument("--shallow", action="store_true")
    parser.add_argument("--linux-install-root", default="/tools/hw_tool")
    args = parser.parse_args()
    try:
        output = publish(args.version, args.output_root, official=args.official,
                         repository_refs=parse_named_values(args.repo_ref, "--repo-ref"),
                         shallow=args.shallow, linux_install_root=args.linux_install_root)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    print(f"[OK] release verified: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
