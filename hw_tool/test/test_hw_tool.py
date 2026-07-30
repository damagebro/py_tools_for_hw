from __future__ import annotations

import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, call, patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SCRIPT_DIR))

import hw_tool
from tool_registry import ToolSpec


class HwToolTest(unittest.TestCase):
    def test_list_includes_registered_tools(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(hw_tool.main(["list"]), 0)
        self.assertIn("de", output.getvalue())

    def test_forwards_group_arguments(self) -> None:
        with patch("hw_tool.subprocess.run") as run:
            run.return_value.returncode = 7
            self.assertEqual(hw_tool.main(["de", "rtl_dummy", "source.sv", "-m", "stub"]), 7)
        command = run.call_args.args[0]
        self.assertEqual(command[-4:], ["rtl_dummy", "source.sv", "-m", "stub"])
        self.assertIn("hw_tool_de.py", command[2])
        self.assertIn("hw_tool_de", run.call_args.kwargs["env"]["HW_TOOL_HOME"])
        self.assertTrue(run.call_args.kwargs["env"]["HW_TOOL_GROUPS_ROOT"].endswith("hw_tool\\groups"))

    def test_unknown_tool_returns_error(self) -> None:
        self.assertEqual(hw_tool.main(["unknown-tool"]), 2)

    def test_help_runs_child_help(self) -> None:
        with patch("hw_tool.subprocess.run") as run:
            run.return_value.returncode = 0
            self.assertEqual(hw_tool.main(["help", "de"]), 0)
        self.assertEqual(run.call_args.args[0][-1], "list")

    def test_sync_all_propagates_to_groups(self) -> None:
        with patch("hw_tool.run_tool", return_value=0) as run:
            self.assertEqual(hw_tool.main(["sync", "--all"]), 0)
        self.assertEqual(run.call_args.args[1], ["sync", "--all"])

    def test_sync_local_group_propagates_to_group_tools(self) -> None:
        with patch("hw_tool.run_tool", return_value=0) as run:
            self.assertEqual(hw_tool.main(["sync", "de"]), 0)
        self.assertEqual(run.call_args.args[1], ["sync", "--all"])

    def test_sync_git_tool_clones_missing_checkout(self) -> None:
        group = ToolSpec(
            name="dv",
            script="groups/hw_tool_dv/src/hw_tool_dv.py",
            description="DV tools.",
            usage="hw_tool dv <tool> [args]",
            kind="hub",
            tool_home="groups/hw_tool_dv",
            source="git",
            repository="ssh://git@example/hw_tool_dv.git",
            branch="main",
        )
        path = MagicMock()
        path.exists.return_value = False
        with patch("hw_tool.tool_home_path", return_value=path):
            with patch("hw_tool.run_git") as run_git:
                hw_tool.sync_git_tool(group)
        self.assertIn("clone", run_git.call_args.args[0])
        self.assertIn("main", run_git.call_args.args[0])
        self.assertIn(group.repository, run_git.call_args.args[0])

    def test_sync_git_tool_updates_clean_checkout(self) -> None:
        group = ToolSpec(
            name="dv",
            script="groups/hw_tool_dv/src/hw_tool_dv.py",
            description="DV tools.",
            usage="hw_tool dv <tool> [args]",
            kind="hub",
            tool_home="groups/hw_tool_dv",
            source="git",
            repository="ssh://git@example/hw_tool_dv.git",
            branch="main",
        )
        path = MagicMock()
        path.exists.return_value = True
        (path / ".git").exists.return_value = True
        status = MagicMock()
        status.stdout = ""
        with patch("hw_tool.tool_home_path", return_value=path):
            with patch("hw_tool.run_git", return_value=status) as run_git:
                hw_tool.sync_git_tool(group)
        self.assertEqual(
            run_git.call_args_list,
            [
                call(["git", "status", "--porcelain"], path),
                call(["git", "fetch", "origin", "main"], path),
                call(["git", "checkout", "main"], path),
                call(["git", "pull", "--ff-only", "origin", "main"], path),
            ],
        )

    def test_implicit_tool_prefers_default_group(self) -> None:
        default_group = hw_tool.get_tool("de")
        dv_group = ToolSpec(
            name="dv",
            script="groups/hw_tool_dv/src/hw_tool_dv.py",
            description="DV tools.",
            usage="hw_tool dv <tool> [args]",
            kind="hub",
            tool_home="groups/hw_tool_dv",
        )
        with patch(
            "hw_tool.global_tool_index",
            return_value={"report": [dv_group, default_group]},
        ):
            self.assertEqual(hw_tool.resolve_implicit_tool("report"), default_group)

    def test_implicit_tool_reports_unresolved_conflict(self) -> None:
        dv_group = ToolSpec(
            name="dv",
            script="groups/hw_tool_dv/src/hw_tool_dv.py",
            description="DV tools.",
            usage="hw_tool dv <tool> [args]",
            kind="hub",
            tool_home="groups/hw_tool_dv",
        )
        soc_group = ToolSpec(
            name="soc",
            script="groups/hw_tool_soc/src/hw_tool_soc.py",
            description="SoC tools.",
            usage="hw_tool soc <tool> [args]",
            kind="hub",
            tool_home="groups/hw_tool_soc",
        )
        with patch(
            "hw_tool.global_tool_index",
            return_value={"report": [dv_group, soc_group]},
        ):
            with self.assertRaisesRegex(hw_tool.HwToolError, "dv, soc"):
                hw_tool.resolve_implicit_tool("report")

    def test_implicit_tool_cli_forwards_to_de(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", "src/hw_tool.py", "mem_tool", "--help"],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Generate memory shells", completed.stdout)

    def test_implicit_doc_cli_forwards_to_de(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", "src/hw_tool.py", "doc", "csr_tool"],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(completed.stdout.startswith("# CSR Autogen Tool"))


if __name__ == "__main__":
    unittest.main()
