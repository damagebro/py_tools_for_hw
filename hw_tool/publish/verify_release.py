#!/usr/bin/env python3
"""Verify a release bundle or its installed hw_tool directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, BadZipFile


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def files_under(root: Path) -> dict[str, Path]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"release must not contain symlinks: {path}")
        if path.is_file():
            relative = path.relative_to(root)
            if "__pycache__" in relative.parts or path.suffix == ".pyc":
                continue
            files[relative.as_posix()] = path
    return files


def write_checksums(root: Path) -> None:
    lines = []
    for name, path in files_under(root).items():
        if name == "SHA256SUMS":
            continue
        if any(character in name for character in "\r\n\\"):
            raise ValueError(f"unsupported checksum filename: {name!r}")
        lines.append(f"{digest(path)}  {name}\n")
    (root / "SHA256SUMS").write_text("".join(lines), encoding="utf-8", newline="\n")


def verify_checksums(root: Path) -> dict[str, Path]:
    actual = files_under(root)
    expected = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise ValueError("invalid SHA256SUMS entry")
        checksum, name = match.groups()
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name or name in expected:
            raise ValueError(f"invalid checksum path: {name}")
        expected[name] = checksum
    if set(expected) != set(actual) - {"SHA256SUMS"}:
        raise ValueError("checksum file inventory mismatch (missing or unexpected files)")
    for name, checksum in expected.items():
        if digest(actual[name]) != checksum:
            raise ValueError(f"SHA256 mismatch: {name}")
    return actual


def check_archive(archive: ZipFile, prefix: str, files: dict[str, Path]) -> None:
    names = [item.filename for item in archive.infolist() if not item.is_dir()]
    if len(names) != len(set(names)):
        raise ValueError("duplicate archive entries")
    scoped = {name for name in names if name.startswith(prefix)}
    expected = {prefix + name for name in files}
    if scoped != expected:
        raise ValueError(f"archive runtime inventory mismatch: {prefix}")
    for name, path in files.items():
        with archive.open(prefix + name) as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        if checksum != digest(path):
            raise ValueError(f"archive runtime content mismatch: {prefix}{name}")


def verify_release(root: Path) -> dict:
    root = root.resolve()
    verify_checksums(root)
    tool_root = root if (root / "release_info.toml").is_file() else root / "hw_tool"
    tool_files = verify_checksums(tool_root)
    metadata = tomllib.loads((tool_root / "release_info.toml").read_text(encoding="utf-8"))
    version = metadata["release"]["version"]
    from build_release import validate_version
    validate_version(version)
    repository = metadata["repository"]["py_tools_for_hw"]
    if not re.fullmatch(r"[0-9a-f]{40}", repository["commit"]):
        raise ValueError("invalid source commit")
    if metadata["release"]["official"]:
        if repository["dirty"] or repository["source"] != "url" or repository["branch"]:
            raise ValueError("invalid official source metadata")
        if repository["ref_kind"] == "tag":
            if repository["tag"] != repository["ref"]:
                raise ValueError("tag metadata mismatch")
        elif repository["ref_kind"] != "commit" or repository["ref"].lower() != repository["commit"] or repository["tag"]:
            raise ValueError("commit metadata mismatch")
    for entry in ("src/hw_tool.py", "bin/hw_tool", "bin/hw_tool.cmd", "hw_tool_de/src/hw_tool_de.py"):
        if entry not in tool_files:
            raise ValueError(f"missing launcher: {entry}")
    documents = json.loads((tool_root / "tool_docs.json").read_text(encoding="utf-8"))
    for item in documents["tools"]:
        if item["readme"] not in tool_files or item["entry"] not in tool_files:
            raise ValueError(f"missing registered tool: {item['name']}")
    if tool_root == root:
        return metadata
    module_path = root / "modulefiles" / "hw_tool" / version
    if f"setenv HW_TOOL_VERSION {version}\n" not in module_path.read_text(encoding="utf-8"):
        raise ValueError("modulefile version mismatch")
    with ZipFile(root / f"hw_tool-{version}.zip") as archive:
        check_archive(archive, "hw_tool/", tool_files)
        for name in ("hw_tool/bin/hw_tool", "hw_tool/hw_tool_de/bin/hw_tool_de"):
            if not archive.getinfo(name).external_attr >> 16 & 0o111 or b"\r\n" in archive.read(name):
                raise ValueError(f"invalid Linux launcher permissions or line endings: {name}")
        name = module_path.relative_to(root).as_posix()
        if archive.read(name) != module_path.read_bytes():
            raise ValueError("ZIP modulefile mismatch")
    vsix = root / f"dmg-hw-tool-{version}.vsix"
    if not vsix.exists():
        return metadata  # The legacy source-only builder does not emit an extension.
    with ZipFile(vsix) as archive:
        check_archive(archive, "extension/runtime/hw_tool/", tool_files)
        for name, path in files_under(tool_root / "publish/vscode").items():
            if PurePosixPath(name).parts[0] in {".vscode", "node_modules", "out", "scripts", "test"} or name in {".gitignore", ".vscodeignore"}:
                continue
            if archive.read("extension/" + name) != path.read_bytes():
                raise ValueError(f"VSIX extension content mismatch: {name}")
        package = json.loads(archive.read("extension/package.json"))
        manifest = ET.fromstring(archive.read("extension.vsixmanifest"))
        identity = manifest.find("{*}Metadata/{*}Identity")
        if package["version"] != version or identity is None or identity.get("Version") != version:
            raise ValueError("VSIX version mismatch")
        for snippet in package.get("contributes", {}).get("snippets", []):
            archive.read("extension/" + snippet["path"].removeprefix("./"))
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        metadata = verify_release(args.directory)
    except (OSError, ValueError, KeyError, BadZipFile, ET.ParseError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    print(f"[OK] verified {metadata['release']['version']}: {args.directory.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
