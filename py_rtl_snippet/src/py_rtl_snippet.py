#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SNIPPET_MD_PATH = Path(__file__).resolve().parents[1] / "input" / "rtl_snippets.md"
SNIPPET_JSON_PATH = (
    Path(__file__).resolve().parents[1]
    / "snippets"
    / "systemverilog.code-snippets"
)
ALWAYS_PREFIXES = (
    "rtl-always_dff_no_rst",
    "rtl-always_dff",
    "rtl-always_dff_begin_end",
    "rtl-always_comb",
)
PORT_PREFIXES = (
    "rtl-vld_rdy",
    "rtl-ram_port",
    "rtl-csr_port",
    "rtl-ebus_rdport",
    "rtl-ebus_wrport",
    "rtl-apb_port",
    "rtl-axi4_port",
)
DEFAULT_PLACEHOLDER_RE = re.compile(r"\$\{(\d+):([^{}]*)\}")
REFERENCE_PLACEHOLDER_RE = re.compile(r"\$\{(\d+)\}|\$(\d+)")
SECTION_RE = re.compile(r"(?ms)^##\s+(?P<prefix>\S+)\s*\n(?P<content>.*?)(?=^##\s+|\Z)")
META_RE = re.compile(r"(?m)^-\s*(?P<key>title|description|scope)\s*:\s*(?P<value>.+?)\s*$")
CODE_BLOCK_RE = re.compile(r"(?ms)^```(?:systemverilog|verilog|sv)\s*\n(?P<body>.*?)^```\s*$")


def parse_snippet_markdown(input_path: Path) -> dict[str, object]:
    try:
        source = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"failed to read snippet Markdown: {exc}") from exc

    snippets: dict[str, object] = {}
    prefixes: set[str] = set()
    for section in SECTION_RE.finditer(source):
        prefix = section.group("prefix")
        content = section.group("content")
        metadata = {
            match.group("key"): match.group("value")
            for match in META_RE.finditer(content)
        }
        code_match = CODE_BLOCK_RE.search(content)
        if code_match is None:
            raise RuntimeError(f"snippet '{prefix}' has no SystemVerilog code block")
        if prefix in prefixes:
            raise RuntimeError(f"duplicate snippet prefix: {prefix}")

        title = metadata.get("title", prefix)
        if title in snippets:
            raise RuntimeError(f"duplicate snippet title: {title}")
        body = code_match.group("body").rstrip("\r\n").splitlines()
        if not body:
            raise RuntimeError(f"snippet '{prefix}' has an empty code block")
        snippets[title] = {
            "scope": metadata.get("scope", "systemverilog,verilog"),
            "prefix": prefix,
            "description": metadata.get("description", prefix),
            "body": body,
        }
        prefixes.add(prefix)

    if not snippets:
        raise RuntimeError(f"no snippets found in {input_path}")
    return snippets


def load_snippets(input_path: Path = SNIPPET_MD_PATH) -> dict[str, object]:
    return parse_snippet_markdown(input_path)


def write_snippets(snippets: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snippets, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def expand_defaults(body: list[str], cursor_text: str = "") -> list[str]:
    values: dict[str, str] = {}

    def replace_default(match: re.Match[str]) -> str:
        index, value = match.groups()
        values.setdefault(index, value)
        return value

    def replace_reference(match: re.Match[str]) -> str:
        index = match.group(1) or match.group(2)
        if index == "0":
            return "$0"
        return values.get(index, "")

    lines: list[str] = []
    for line in body:
        line = DEFAULT_PLACEHOLDER_RE.sub(replace_default, line)
        line = REFERENCE_PLACEHOLDER_RE.sub(replace_reference, line)
        lines.append(line.replace("$0", cursor_text))
    return lines


def snippet_body(snippets: dict[str, object], title: str, cursor_text: str = "") -> list[str]:
    item = snippets.get(title)
    if not isinstance(item, dict):
        raise RuntimeError(f"snippet not found: {title}")
    body = item.get("body")
    if not isinstance(body, list) or not all(isinstance(line, str) for line in body):
        raise RuntimeError(f"snippet '{title}' has an invalid body")
    return expand_defaults(body, cursor_text)


def title_for_prefix(snippets: dict[str, object], prefix: str) -> str | None:
    for title, item in snippets.items():
        if isinstance(item, dict) and item.get("prefix") == prefix:
            return title
    return None


def generate_preview(snippets: dict[str, object], output_path: Path) -> None:
    sections: list[list[str]] = [
        [
            "// Generated preview for py_rtl_snippet.",
            "// This file expands default placeholders for syntax review only.",
            "",
        ],
    ]
    module_title = title_for_prefix(snippets, "rtl-module")
    if module_title is not None:
        sections.append(snippet_body(snippets, module_title))

    type_titles = [
        title_for_prefix(snippets, prefix)
        for prefix in ("rtl-struct", "rtl-union", "rtl-enum")
    ]
    if all(title is not None for title in type_titles):
        sections.append(
            [
                "package py_rtl_snippet_types_pkg;",
                "",
                *snippet_body(snippets, type_titles[0]),
                "",
                *snippet_body(snippets, type_titles[1]),
                "",
                *snippet_body(snippets, type_titles[2]),
                "",
                "endpackage",
            ]
        )

    for prefix in ALWAYS_PREFIXES:
        title = title_for_prefix(snippets, prefix)
        if title is not None:
            sections.append(snippet_body(snippets, title))

    for prefix in PORT_PREFIXES:
        title = title_for_prefix(snippets, prefix)
        if title is not None:
            sections.append(snippet_body(snippets, title))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n\n".join("\n".join(section) for section in sections) + "\n"
    output_path.write_text(content, encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse Markdown RTL snippets and generate VS Code snippet JSON."
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--list", action="store_true", help="list snippet prefixes")
    action.add_argument("--print", action="store_true", help="print generated snippet JSON")
    action.add_argument(
        "--preview",
        type=Path,
        metavar="FILE",
        help="generate a SystemVerilog preview with default placeholders expanded",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=SNIPPET_MD_PATH,
        help="snippet Markdown source, default: input/rtl_snippets.md",
    )
    parser.add_argument("-o", "--output", type=Path, help="generated VS Code snippet JSON")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        snippets = load_snippets(args.input)
        if args.preview is not None:
            generate_preview(snippets, args.preview)
            print(f"generated {args.preview} ({len(snippets)} snippets)")
        elif args.output is not None:
            write_snippets(snippets, args.output)
            print(f"generated {args.output} ({len(snippets)} snippets)")
        elif args.print:
            print(json.dumps(snippets, indent=4, ensure_ascii=False))
        else:
            rows = []
            for item in snippets.values():
                if not isinstance(item, dict):
                    raise RuntimeError("snippet entry must be an object")
                rows.append((str(item["prefix"]), str(item["description"])))
            prefix_width = max(len(prefix) for prefix, _ in rows)
            for prefix, description in rows:
                print(f"{prefix:<{prefix_width}}  {description}")
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
