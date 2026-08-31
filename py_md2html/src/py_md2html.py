#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path


VERSION = "0.1.1"
MARKDOWN_SUFFIXES = {".md", ".markdown"}
THEMES = {"auto", "light", "dark"}

PAGE_STYLE = """
:root {
    color-scheme: light;
    --page-bg: #ffffff;
    --page-fg: #1f2328;
    --link-fg: #0969da;
    --border: #d0d7de;
    --code-bg: #eff1f3;
    --panel-bg: #f6f8fa;
    --quote-fg: #57606a;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    line-height: 1.6;
}
:root[data-theme="dark"] {
    color-scheme: dark;
    --page-bg: #0d1117;
    --page-fg: #e6edf3;
    --link-fg: #58a6ff;
    --border: #30363d;
    --code-bg: #21262d;
    --panel-bg: #161b22;
    --quote-fg: #8b949e;
}
body {
    max-width: 1120px;
    margin: 0 auto;
    padding: 32px 28px 64px;
    color: var(--page-fg);
    background: var(--page-bg);
}
a { color: var(--link-fg); }
h1, h2, h3, h4, h5, h6 {
    margin-top: 1.5em;
    margin-bottom: 0.6em;
    line-height: 1.25;
    letter-spacing: 0;
}
h1, h2 { padding-bottom: 0.3em; border-bottom: 1px solid var(--border); }
code, pre { font-family: Consolas, "SFMono-Regular", monospace; }
code { padding: 0.15em 0.35em; background: var(--code-bg); border-radius: 3px; }
pre { overflow: auto; padding: 16px; background: var(--panel-bg); border: 1px solid var(--border); }
pre code { padding: 0; background: transparent; }
table { border-collapse: collapse; width: max-content; max-width: 100%; }
th, td { padding: 6px 13px; border: 1px solid var(--border); text-align: left; }
th { background: var(--panel-bg); }
blockquote { margin-left: 0; padding-left: 16px; color: var(--quote-fg); border-left: 4px solid var(--border); }
img { max-width: 100%; height: auto; }
.toc { padding: 12px 16px; border: 1px solid var(--border); }
@media (prefers-color-scheme: dark) {
    :root[data-theme="auto"] {
        color-scheme: dark;
        --page-bg: #0d1117;
        --page-fg: #e6edf3;
        --link-fg: #58a6ff;
        --border: #30363d;
        --code-bg: #21262d;
        --panel-bg: #161b22;
        --quote-fg: #8b949e;
    }
}
""".strip()


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert one Markdown document to a standalone HTML page."
    )
    parser.add_argument("input", help="Input Markdown file (.md or .markdown)")
    parser.add_argument(
        "-o",
        "--output",
        help="Output HTML file (default: input filename with .html suffix)",
    )
    parser.add_argument("--title", help="Override the HTML page title")
    parser.add_argument(
        "--toc",
        action="store_true",
        help="Insert a generated table of contents before the document",
    )
    parser.add_argument(
        "--theme",
        choices=sorted(THEMES),
        default="auto",
        help="HTML color theme (default: auto)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"py_md2html {VERSION}",
    )
    return parser


def convert_markdown(
    input_path: str | Path,
    output_path: str | Path | None = None,
    title: str | None = None,
    include_toc: bool = False,
    theme: str = "auto",
) -> Path:
    source = Path(input_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Markdown input not found: {source}")
    if source.suffix.lower() not in MARKDOWN_SUFFIXES:
        raise ValueError("Markdown input suffix must be '.md' or '.markdown'")

    output = (
        Path(output_path).expanduser().resolve()
        if output_path is not None
        else source.with_suffix(".html")
    )
    if output.suffix.lower() not in {".html", ".htm"}:
        raise ValueError("HTML output suffix must be '.html' or '.htm'")
    if theme not in THEMES:
        raise ValueError(f"HTML theme must be one of: {', '.join(sorted(THEMES))}")

    try:
        import markdown
    except ImportError as exc:
        raise ImportError(
            "Python-Markdown is required; install with: "
            "python -m pip install -r requirements.txt"
        ) from exc

    markdown_text = source.read_text(encoding="utf-8-sig")
    page_title = title or _document_title(markdown_text, source.stem)
    renderer = markdown.Markdown(
        extensions=["extra", "sane_lists", "toc"],
        extension_configs={"toc": {"permalink": True}},
        output_format="html5",
    )
    body = renderer.convert(markdown_text)
    toc = renderer.toc if include_toc else ""
    base_uri = source.parent.as_uri().rstrip("/") + "/"
    document = _html_document(page_title, base_uri, toc, body, theme)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    return output


def _document_title(markdown_text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", markdown_text, flags=re.MULTILINE)
    return match.group(1).strip() if match else fallback


def _html_document(title: str, base_uri: str, toc: str, body: str, theme: str) -> str:
    escaped_title = html.escape(title, quote=True)
    escaped_base = html.escape(base_uri, quote=True)
    toc_block = f"\n<nav aria-label=\"Table of contents\">{toc}</nav>" if toc else ""
    return f"""<!doctype html>
<html lang="zh-CN" data-theme="{theme}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<base href="{escaped_base}">
<title>{escaped_title}</title>
<style>
{PAGE_STYLE}
</style>
</head>
<body>{toc_block}
<main>
{body}
</main>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        output = convert_markdown(
            args.input,
            args.output,
            title=args.title,
            include_toc=args.toc,
            theme=args.theme,
        )
    except (FileNotFoundError, ImportError, OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    print(f"[OK] HTML generated: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
