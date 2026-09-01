#!/usr/bin/env python3
"""Create an offline-installable VS Code extension package without vsce."""

from __future__ import annotations

import argparse
import json
import sys
import xml.sax.saxutils
import zipfile
from pathlib import Path


EXTENSION_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = EXTENSION_ROOT / "out" / "dmg-hw-tool-0.4.0.vsix"
EXCLUDED_DIRECTORIES = {
    ".vscode",
    "node_modules",
    "out",
    "scripts",
    "test",
}
EXCLUDED_FILES = {".gitignore", ".vscodeignore"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package the HW Tool VS Code extension.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def package_metadata() -> dict[str, object]:
    try:
        data = json.loads((EXTENSION_ROOT / "package.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"failed to load package.json: {exc}") from exc
    required = ("name", "displayName", "description", "publisher", "version", "engines")
    if any(not data.get(key) for key in required):
        raise ValueError("package.json is missing required VS Code extension metadata")
    return data


def extension_files() -> list[Path]:
    files: list[Path] = []
    for path in EXTENSION_ROOT.rglob("*"):
        relative = path.relative_to(EXTENSION_ROOT)
        if any(part in EXCLUDED_DIRECTORIES for part in relative.parts[:-1]):
            continue
        if path.is_dir() or path.name in EXCLUDED_FILES:
            continue
        if path.suffix in {".pyc", ".vsix"} or "__pycache__" in relative.parts:
            continue
        files.append(path)
    return sorted(files)


def vsix_manifest(metadata: dict[str, object]) -> str:
    engines = metadata["engines"]
    engine = engines.get("vscode", "*") if isinstance(engines, dict) else "*"
    values = {
        "name": xml.sax.saxutils.escape(str(metadata["name"])),
        "display_name": xml.sax.saxutils.escape(str(metadata["displayName"])),
        "description": xml.sax.saxutils.escape(str(metadata["description"])),
        "publisher": xml.sax.saxutils.escape(str(metadata["publisher"])),
        "version": xml.sax.saxutils.escape(str(metadata["version"])),
        "engine": xml.sax.saxutils.escape(str(engine)),
    }
    return """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<PackageManifest Version=\"2.0.0\" xmlns=\"http://schemas.microsoft.com/developer/vsx-schema/2011\">
  <Metadata>
    <Identity Language=\"en-US\" Id=\"{name}\" Version=\"{version}\" Publisher=\"{publisher}\" />
    <DisplayName>{display_name}</DisplayName>
    <Description xml:space=\"preserve\">{description}</Description>
    <Categories>Snippets,Other</Categories>
    <Properties>
      <Property Id=\"Microsoft.VisualStudio.Code.Engine\" Value=\"{engine}\" />
    </Properties>
  </Metadata>
  <Installation>
    <InstallationTarget Id=\"Microsoft.VisualStudio.Code\" />
  </Installation>
  <Dependencies />
  <Assets>
    <Asset Type=\"Microsoft.VisualStudio.Code.Manifest\" Path=\"extension/package.json\" Addressable=\"true\" />
  </Assets>
</PackageManifest>
""".format(**values)


def content_types() -> str:
    return """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
  <Default Extension=\"json\" ContentType=\"application/json\" />
  <Default Extension=\"js\" ContentType=\"application/javascript\" />
  <Default Extension=\"md\" ContentType=\"text/markdown\" />
  <Default Extension=\"xml\" ContentType=\"application/xml\" />
  <Default Extension=\"vsixmanifest\" ContentType=\"text/xml\" />
</Types>
"""


def package_extension(output_path: Path) -> int:
    metadata = package_metadata()
    runtime_entry = EXTENSION_ROOT / "runtime" / "hw_tool" / "src" / "hw_tool.py"
    if not runtime_entry.is_file():
        print("[ERROR] runtime is missing; run: npm run sync-runtime", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extension.vsixmanifest", vsix_manifest(metadata))
        archive.writestr("[Content_Types].xml", content_types())
        for source_path in extension_files():
            relative_path = source_path.relative_to(EXTENSION_ROOT).as_posix()
            archive.write(source_path, f"extension/{relative_path}")

    print(f"[OK] VSIX package: {output_path.resolve()}")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return package_extension(args.output)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
