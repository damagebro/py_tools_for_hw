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
