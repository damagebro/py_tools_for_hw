from __future__ import annotations

import subprocess
import sys
import unittest
import json
from pathlib import Path


GROUP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GROUP_ROOT / "src"))

from tool_registry import REPOSITORY_MAP, TOOL_MAP


class HwToolDeTest(unittest.TestCase):
    def test_tools_share_repository_sources(self) -> None:
        self.assertEqual(
            REPOSITORY_MAP["py_tools_for_hw"].repository,
            "https://github.com/damagebro/py_tools_for_hw.git",
        )
        self.assertEqual(
            REPOSITORY_MAP["py_tools_for_hw"].workspace,
            "../..",
        )
        self.assertEqual(TOOL_MAP["csr_tool"].repository_name, "py_tools_for_hw")
        self.assertEqual(TOOL_MAP["rtl_inst"].repository_name, "py_tools_for_hw")
        self.assertEqual(TOOL_MAP["rtl_dummy"].repository_name, "py_tools_for_hw")
        self.assertEqual(TOOL_MAP["gen_tb"].repository_name, "py_tools_for_hw")
        self.assertEqual(TOOL_MAP["md2html"].repository_name, "py_tools_for_hw")
        self.assertEqual(TOOL_MAP["git_repo_mgr"].repository_name, "py_tools_for_hw")
        self.assertEqual(TOOL_MAP["rtl_flist_mgr"].repository_name, "py_tools_for_hw")
        self.assertEqual(TOOL_MAP["mem_tool"].repository_name, "py_tools_for_hw")
        self.assertEqual(TOOL_MAP["csr_tool"].doctor_packages, ("jinja2", "openpyxl"))
        self.assertEqual(TOOL_MAP["mem_tool"].doctor_packages, ("openpyxl",))
        for name in (
            "rtl_inst",
            "rtl_dummy",
            "csr_tool",
            "gen_tb",
            "md2html",
            "git_repo_mgr",
            "rtl_flist_mgr",
            "mem_tool",
        ):
            tool = TOOL_MAP[name]
            self.assertTrue(tool.example)
            self.assertTrue(tool.smoke_args)
            self.assertTrue(tool.smoke_outputs or tool.smoke_stdout)
            self.assertTrue(tool.unit_tests)

    def test_list_runs_from_group_entry(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", "src/hw_tool_de.py", "list"],
            cwd=GROUP_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("mem_tool", completed.stdout)
        self.assertIn("rtl_inst", completed.stdout)
        self.assertIn("rtl_dummy", completed.stdout)
        self.assertIn("csr_tool", completed.stdout)
        self.assertIn("gen_tb", completed.stdout)
        self.assertIn("md2html", completed.stdout)
        self.assertIn("git_repo_mgr", completed.stdout)
        self.assertIn("rtl_flist_mgr", completed.stdout)
        self.assertNotIn("missing", completed.stdout)

    def test_version_shows_group_repository_commit(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", "src/hw_tool_de.py", "--version"],
            cwd=GROUP_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(completed.stdout.startswith("hw_tool_de: "))

    def test_verify_checks_registered_tool_contracts(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", "src/hw_tool_de.py", "verify"],
            cwd=GROUP_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("rtl_inst: contract", completed.stdout)
        self.assertIn("gen_tb: contract", completed.stdout)
        self.assertIn("md2html: contract", completed.stdout)
        self.assertIn("git_repo_mgr: contract", completed.stdout)
        self.assertIn("rtl_flist_mgr: contract", completed.stdout)
        self.assertIn("mem_tool: contract", completed.stdout)

    def test_sync_dry_run_is_non_mutating(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", "src/hw_tool_de.py", "sync", "mem_tool", "--dry-run"],
            cwd=GROUP_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertRegex(completed.stdout, r"would (clone|update|use)")

    def test_help_shows_document_url(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", "src/hw_tool_de.py", "help", "csr_tool"],
            cwd=GROUP_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("document: https://github.com/damagebro/py_tools_for_hw/", completed.stdout)
        self.assertIn("csr_tool/README.md", completed.stdout)

    def test_list_json_is_machine_readable(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", "src/hw_tool_de.py", "list", "--json"],
            cwd=GROUP_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        tools = {tool["name"]: tool for tool in payload["tools"]}
        self.assertIn("mem_tool", tools)
        self.assertEqual(tools["mem_tool"]["status"], "ready")
        self.assertRegex(
            tools["mem_tool"]["detail"] or "",
            r"^(?:workspace )?[0-9a-f]+(?: dirty)?$",
        )

    def test_doc_prints_mem_tool_readme(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", "src/hw_tool_de.py", "doc", "mem_tool"],
            cwd=GROUP_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(completed.stdout.startswith("# Memory Tool"))
        self.assertIn("truncated at lines 1-48", completed.stdout)

    def test_doc_all_prints_complete_readme(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", "src/hw_tool_de.py", "doc", "mem_tool", "--all"],
            cwd=GROUP_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("... truncated", completed.stdout)


if __name__ == "__main__":
    unittest.main()
