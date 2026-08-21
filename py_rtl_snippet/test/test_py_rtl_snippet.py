from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SCRIPT_DIR))

from py_rtl_snippet import SNIPPET_MD_PATH, load_snippets, main


class PyRtlSnippetTest(unittest.TestCase):
    def make_workdir(self) -> Path:
        path = Path(__file__).resolve().parent / "_work" / uuid.uuid4().hex
        path.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path

    def test_markdown_library_has_required_prefixes(self) -> None:
        snippets = load_snippets()
        prefixes = {
            item["prefix"]
            for item in snippets.values()
            if isinstance(item, dict) and isinstance(item.get("prefix"), str)
        }
        self.assertTrue(SNIPPET_MD_PATH.is_file())
        self.assertTrue(
            {"rtl-dff-an", "rtl-comb", "csr-port", "axi4-port"} <= prefixes
        )
        self.assertNotIn("rtl-dff-sync", prefixes)
        self.assertFalse(any(prefix.endswith("-if") for prefix in prefixes))
        self.assertTrue(all(isinstance(item["body"], list) for item in snippets.values()))

    def test_main_exports_valid_json(self) -> None:
        output_path = self.make_workdir() / "out" / "systemverilog.code-snippets"
        self.assertEqual(main(["-o", str(output_path)]), 0)
        self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), load_snippets())

    def test_main_parses_custom_markdown(self) -> None:
        workdir = self.make_workdir()
        input_path = workdir / "custom.md"
        output_path = workdir / "custom.code-snippets"
        input_path.write_text(
            "\n".join(
                [
                    "## rtl-custom",
                    "",
                    "- title: RTL custom",
                    "- description: Custom snippet.",
                    "",
                    "```systemverilog",
                    "assign ${1:o_data} = ${2:i_data};${0}",
                    "```",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        self.assertEqual(main(["-i", str(input_path), "-o", str(output_path)]), 0)
        snippets = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(snippets["RTL custom"]["prefix"], "rtl-custom")

    def test_main_generates_systemverilog_preview(self) -> None:
        output_path = self.make_workdir() / "out" / "py_rtl_snippet_preview.sv"
        self.assertEqual(main(["--preview", str(output_path)]), 0)
        content = output_path.read_text(encoding="utf-8")
        self.assertIn("module module_name", content)
        self.assertIn("always @(posedge clk) begin", content)
        self.assertNotIn("module py_rtl_snippet_rtl_clocked_always", content)
        self.assertIn("package py_rtl_snippet_types_pkg;", content)
        self.assertIn("output wire [AW-1:0]            o_tx_axi_awaddr", content)
        self.assertNotIn("module py_rtl_snippet_axi4_ports", content)
        self.assertNotIn("interface ", content)
        self.assertNotIn("${", content)
        self.assertNotIn("$0", content)


if __name__ == "__main__":
    unittest.main()
