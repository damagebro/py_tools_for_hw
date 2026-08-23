from __future__ import annotations

import io
import json
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
        self.assertTrue(
            run.call_args.kwargs["env"]["HW_TOOL_REPOSITORY_ROOT"].endswith(
                "hw_tool\\repository"
            )
        )

    def test_unknown_tool_returns_error(self) -> None:
        self.assertEqual(hw_tool.main(["unknown-tool"]), 2)

    def test_help_runs_child_help(self) -> None:
        with patch("hw_tool.subprocess.run") as run:
            run.return_value.returncode = 0
            self.assertEqual(hw_tool.main(["help", "de"]), 0)
        self.assertEqual(run.call_args.args[0][-1], "list")

    def test_version_uses_git_description(self) -> None:
        output = io.StringIO()
        with patch("hw_tool.git_version", return_value="v1.2.3-4-g1234567-dirty"):
            with patch("hw_tool.git_commit_date", return_value="2026-07-31 09:30"):
                with redirect_stdout(output):
                    self.assertEqual(hw_tool.main(["--version"]), 0)
        self.assertIn(
            "hw_tool: v1.2.3-4-g1234567-dirty (2026-07-31 09:30)",
            output.getvalue(),
        )

    def test_doctor_propagates_to_ready_groups(self) -> None:
        with patch("hw_tool.print_doctor_report", return_value=0):
            with patch("hw_tool.run_tool", return_value=0) as run:
                self.assertEqual(hw_tool.main(["doctor"]), 0)
        self.assertEqual(run.call_args.args[1], ["doctor"])

    def test_verify_propagates_to_ready_groups(self) -> None:
        with patch("hw_tool.run_tool", return_value=0) as run:
            self.assertEqual(hw_tool.main(["verify"]), 0)
        self.assertEqual(run.call_args.args[1], ["verify"])

    def test_test_all_propagates_to_ready_groups(self) -> None:
        with patch("hw_tool.run_tool", return_value=0) as run:
            self.assertEqual(hw_tool.main(["test", "--all"]), 0)
        self.assertEqual(run.call_args.args[1], ["test", "--all"])

    def test_help_doctor(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(hw_tool.main(["help", "doctor"]), 0)
        self.assertIn("usage: hw_tool doctor", output.getvalue())

    def test_sync_all_propagates_to_groups(self) -> None:
        with patch("hw_tool.run_tool", return_value=0) as run:
            self.assertEqual(hw_tool.main(["sync", "--all"]), 0)
        self.assertEqual(run.call_args.args[1], ["sync", "--all"])

    def test_sync_dry_run_propagates_to_groups(self) -> None:
        with patch("hw_tool.run_tool", return_value=0) as run:
            self.assertEqual(hw_tool.main(["sync", "--all", "--dry-run"]), 0)
        self.assertEqual(run.call_args.args[1], ["sync", "--all", "--dry-run"])

    def test_sync_shallow_propagates_to_groups(self) -> None:
        with patch("hw_tool.run_tool", return_value=0) as run:
            self.assertEqual(hw_tool.main(["sync", "--all", "--shallow"]), 0)
        self.assertEqual(run.call_args.args[1], ["sync", "--all", "--shallow"])

    def test_sync_local_group_propagates_to_group_tools(self) -> None:
        with patch("hw_tool.run_tool", return_value=0) as run:
            self.assertEqual(hw_tool.main(["sync", "de"]), 0)
        self.assertEqual(run.call_args.args[1], ["sync", "--all"])

    def test_sync_git_tool_clones_missing_checkout(self) -> None:
        group = ToolSpec(
            name="dv",
            script="repository/hw_tool_dv/src/hw_tool_dv.py",
            description="DV tools.",
            usage="hw_tool dv <tool> [args]",
            kind="hub",
            tool_home="repository/hw_tool_dv",
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

    def test_sync_git_tool_dry_run_does_not_clone(self) -> None:
        group = ToolSpec(
            name="dv",
            script="repository/hw_tool_dv/src/hw_tool_dv.py",
            description="DV tools.",
            usage="hw_tool dv <tool> [args]",
            kind="hub",
            tool_home="repository/hw_tool_dv",
            source="git",
            repository="ssh://git@example/hw_tool_dv.git",
            branch="main",
        )
        path = MagicMock()
        path.exists.return_value = False
        with patch("hw_tool.tool_home_path", return_value=path):
            with patch("hw_tool.run_git") as run_git:
                hw_tool.sync_git_tool(group, dry_run=True)
        run_git.assert_not_called()

    def test_sync_git_tool_shallow_clone_uses_depth_one(self) -> None:
        group = ToolSpec(
            name="dv",
            script="repository/hw_tool_dv/src/hw_tool_dv.py",
            description="DV tools.",
            usage="hw_tool dv <tool> [args]",
            kind="hub",
            tool_home="repository/hw_tool_dv",
            source="git",
            repository="ssh://git@example/hw_tool_dv.git",
            branch="main",
        )
        path = MagicMock()
        path.exists.return_value = False
        with patch("hw_tool.tool_home_path", return_value=path):
            with patch("hw_tool.run_git") as run_git:
                hw_tool.sync_git_tool(group, shallow=True)
        self.assertIn("--depth", run_git.call_args.args[0])
        self.assertIn("1", run_git.call_args.args[0])

    def test_sync_git_tool_dry_run_skips_dirty_checkout(self) -> None:
        group = ToolSpec(
            name="dv",
            script="repository/hw_tool_dv/src/hw_tool_dv.py",
            description="DV tools.",
            usage="hw_tool dv <tool> [args]",
            kind="hub",
            tool_home="repository/hw_tool_dv",
            source="git",
            repository="ssh://git@example/hw_tool_dv.git",
            branch="main",
        )
        path = MagicMock()
        path.exists.return_value = True
        (path / ".git").exists.return_value = True
        status = MagicMock()
        status.stdout = " M README.md"
        with patch("hw_tool.tool_home_path", return_value=path):
            with patch("hw_tool.run_git", return_value=status) as run_git:
                hw_tool.sync_git_tool(group, dry_run=True)
        self.assertEqual(run_git.call_count, 1)

    def test_sync_git_tool_updates_clean_checkout(self) -> None:
        group = ToolSpec(
            name="dv",
            script="repository/hw_tool_dv/src/hw_tool_dv.py",
            description="DV tools.",
            usage="hw_tool dv <tool> [args]",
            kind="hub",
            tool_home="repository/hw_tool_dv",
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
        default_tool = hw_tool.FederatedTool(
            name="report",
            qualified_name="de.report",
            route=("de", "report"),
            description="DE report.",
            status="ready",
            detail=None,
            doc_url=None,
        )
        dv_tool = hw_tool.FederatedTool(
            name="report",
            qualified_name="dv.report",
            route=("dv", "report"),
            description="DV report.",
            status="ready",
            detail=None,
            doc_url=None,
        )
        with patch(
            "hw_tool.global_tool_index",
            return_value={"report": [dv_tool, default_tool]},
        ):
            self.assertEqual(hw_tool.resolve_implicit_tool("report"), default_tool)

    def test_implicit_tool_reports_unresolved_conflict(self) -> None:
        dv_tool = hw_tool.FederatedTool(
            name="report",
            qualified_name="dv.report",
            route=("dv", "report"),
            description="DV report.",
            status="ready",
            detail=None,
            doc_url=None,
        )
        soc_tool = hw_tool.FederatedTool(
            name="report",
            qualified_name="soc.report",
            route=("soc", "report"),
            description="SoC report.",
            status="ready",
            detail=None,
            doc_url=None,
        )
        with patch(
            "hw_tool.global_tool_index",
            return_value={"report": [dv_tool, soc_tool]},
        ):
            with self.assertRaisesRegex(hw_tool.HwToolError, "dv.report, soc.report"):
                hw_tool.resolve_implicit_tool("report")

    def test_recursive_list_returns_qualified_routes(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", "src/hw_tool.py", "list", "--recursive", "--json"],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        tools = {tool["qualified_name"]: tool for tool in payload["tools"]}
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(tools["de.csr_tool"]["route"], ["de", "csr_tool"])

    def test_run_qualified_tool_forwards_full_route(self) -> None:
        with patch("hw_tool.run_tool", return_value=0) as run:
            self.assertEqual(hw_tool.main(["run", "de.csr_tool", "--help"]), 0)
        self.assertEqual(run.call_args.args[1], ["csr_tool", "--help"])

    def test_detects_hub_integration_cycle(self) -> None:
        with patch.dict("hw_tool.os.environ", {"HW_TOOL_HUB_CHAIN": "py_tools_for_hw"}):
            self.assertEqual(hw_tool.main(["list"]), 2)

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
