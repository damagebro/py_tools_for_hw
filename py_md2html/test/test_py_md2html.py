from __future__ import annotations

import shutil
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from py_md2html import VERSION, convert_markdown, main


class WorkspaceTemporaryDirectory:
    def __init__(self) -> None:
        self.path = ROOT / ".test_work" / uuid.uuid4().hex

    def __enter__(self) -> Path:
        self.path.mkdir(parents=True)
        return self.path

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        shutil.rmtree(self.path, ignore_errors=True)
        try:
            self.path.parent.rmdir()
        except OSError:
            pass


class MarkdownToHtmlTests(unittest.TestCase):
    def test_numbers_headings_and_toc_without_changing_source_or_links(self) -> None:
        with WorkspaceTemporaryDirectory() as directory:
            source = directory / "guide.md"
            text = "# Guide\n\n[Details](#details)\n\n## Overview\n\n### **Details**\n\n## Next\n\n```md\n# Example\n```\n"
            source.write_text(text, encoding="utf-8")
            document = convert_markdown(source, stdout=True, include_toc=True, number_headings=True)
            self.assertIn('<h1 id="guide">Guide', document)
            self.assertIn('<h2 id="overview">1. Overview', document)
            self.assertIn('<h3 id="details">1.1 <strong>Details</strong>', document)
            self.assertIn('<h2 id="next">2. Next', document)
            self.assertIn('href="#details">1.1 Details</a>', document)
            self.assertIn('href="#details">Details</a>', document)
            self.assertIn('# Example\n</code>', document)
            self.assertEqual(source.read_text(encoding="utf-8"), text)
            self.assertFalse(source.with_suffix(".html").exists())

    def test_preserves_existing_numbers_and_continues_them(self) -> None:
        with WorkspaceTemporaryDirectory() as directory:
            source = directory / "guide.md"
            for title in ("4. Existing", "四、Existing", "第四章 Existing", "4 Existing", "4.已有编号"):
                with self.subTest(title=title):
                    source.write_text(f"# Guide\n\n## {title}\n\n### Details\n\n## Next\n", encoding="utf-8")
                    document = convert_markdown(source, stdout=True, include_toc=True, number_headings=True)
                    self.assertIn(f">{title}<a", document)
                    self.assertIn('>4.1 Details<a', document)
                    self.assertIn('>5. Next<a', document)

    def test_multiple_h1_skipped_levels_and_explicit_toc_marker(self) -> None:
        with WorkspaceTemporaryDirectory() as directory:
            source = directory / "guide.md"
            source.write_text("[TOC]\n\n# First\n\n### Detail\n\n# Second\n", encoding="utf-8")
            document = convert_markdown(source, stdout=True, include_toc=True, number_headings=True)
            self.assertIn('>1. First<a', document)
            self.assertIn('>1.1 Detail<a', document)
            self.assertIn('>2. Second<a', document)
            self.assertEqual(document.count('href="#detail">1.1 Detail</a>'), 2)

    def test_numbering_cli_and_plain_cli_compatibility(self) -> None:
        with WorkspaceTemporaryDirectory() as directory:
            source = directory / "guide.md"
            source.write_text("# Guide\n\n## Intro\n", encoding="utf-8")
            self.assertEqual(main([str(source), "--toc", "--number-headings"]), 0)
            document = source.with_suffix(".html").read_text(encoding="utf-8")
            self.assertIn('aria-label="Table of contents"', document)
            self.assertIn('>1. Intro<a', document)
            plain = convert_markdown(source, stdout=True)
            self.assertNotIn('aria-label="Table of contents"', plain)
            self.assertIn('>Intro<a', plain)

    def test_stdout_does_not_create_or_overwrite_html(self) -> None:
        with WorkspaceTemporaryDirectory() as directory:
            source = directory / "preview.md"
            source.write_text("# Preview\n\n## Section\n", encoding="utf-8")
            document = convert_markdown(source, stdout=True, include_toc=True, theme="dark")
            self.assertIn('class="toc"', document)
            self.assertIn('data-theme="dark"', document)
            self.assertEqual([source], list(directory.iterdir()))
            existing = source.with_suffix(".html")
            existing.write_text("keep", encoding="utf-8")
            convert_markdown(source, stdout=True)
            self.assertEqual("keep", existing.read_text(encoding="utf-8"))

    def test_converts_common_markdown_and_preserves_asset_root(self) -> None:
        with WorkspaceTemporaryDirectory() as temporary_directory:
            source = temporary_directory / "guide.md"
            output = temporary_directory / "out" / "guide.html"
            source.write_text(
                "# Hardware Guide\n\n"
                "## Table\n\n"
                "| name | value |\n"
                "| ---- | ----- |\n"
                "| csr  | 1     |\n\n"
                "```systemverilog\nlogic valid;\n```\n\n"
                "![diagram](assets/diagram.png)\n",
                encoding="utf-8",
            )
            generated = convert_markdown(source, output, include_toc=True)
            document = generated.read_text(encoding="utf-8")
            self.assertEqual(output.resolve(), generated)
            self.assertIn("<title>Hardware Guide</title>", document)
            self.assertIn("<table>", document)
            self.assertIn('class="language-systemverilog"', document)
            self.assertIn('class="toc"', document)
            self.assertIn(source.parent.as_uri(), document)
            self.assertIn('src="assets/diagram.png"', document)
            self.assertIn('data-theme="auto"', document)

    def test_generates_explicit_light_theme(self) -> None:
        with WorkspaceTemporaryDirectory() as temporary_directory:
            source = temporary_directory / "guide.md"
            source.write_text("# Hardware Guide\n", encoding="utf-8")
            generated = convert_markdown(source, theme="light")
            self.assertIn(
                'data-theme="light"',
                generated.read_text(encoding="utf-8"),
            )

    def test_cli_defaults_to_input_stem_html(self) -> None:
        with WorkspaceTemporaryDirectory() as temporary_directory:
            source = temporary_directory / "README.md"
            source.write_text("# Demo\n", encoding="utf-8")
            self.assertEqual(0, main([str(source)]))
            self.assertTrue(source.with_suffix(".html").is_file())

    def test_version_is_defined(self) -> None:
        self.assertRegex(VERSION, r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
