from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tomllib
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SCRIPT_DIR))

import git_repo_mgr as mgr
from admin_policy import PolicyStatus


main = mgr.main


class FakeProviderClient:
    applied: list[tuple[str, str, str]] = []
    restored: list[tuple[str, str]] = []

    def __init__(self, config: object) -> None:
        self.config = config

    def identity(self) -> str:
        return "release-bot"

    def status(self, target: object, branch: str) -> PolicyStatus:
        return PolicyStatus(
            target=target,
            provider=self.config,
            project=f"company/{target.name}",
            protected=True,
            mode="integration-only",
            raw={"mode": "integration-only"},
        )

    def apply_mode(self, project: str, branch: str, mode: str, current: object) -> None:
        self.applied.append((project, branch, mode))

    def restore(self, project: str, branch: str, raw: object) -> None:
        self.restored.append((project, branch))


class GitRepoMgrTest(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(__file__).resolve().parent / "_work" / uuid.uuid4().hex
        self.work.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)

    def git(self, args: list[str], cwd: Path) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            self.fail(f"git {' '.join(args)} failed: {result.stderr or result.stdout}")
        return result.stdout.strip()

    def create_repo(self, name: str, manifest: str = "") -> Path:
        path = self.work / "source" / name
        path.mkdir(parents=True)
        self.git(["init", "-q", "-b", "main"], path)
        self.git(["config", "user.email", "test@example.com"], path)
        self.git(["config", "user.name", "Git Repo Mgr Test"], path)
        (path / "git_deps.toml").write_text(manifest, encoding="utf-8")
        (path / "README.txt").write_text(f"{name}\n", encoding="utf-8")
        self.git(["add", "."], path)
        self.git(["commit", "-q", "-m", "initial"], path)
        return path

    def prepare_top(self, manifest: str) -> Path:
        top = self.create_repo("top", manifest)
        self.git(["remote", "add", "origin", str(top)], top)
        return top

    def invoke(self, args: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def dependency(repository: Path, ref: str = "main") -> str:
        return (
            "[[dependency]]\n"
            f"repository = {json.dumps(str(repository))}\n"
            f"ref = {json.dumps(ref)}\n"
        )

    def test_workspace_discovery_priority_and_ambiguity(self) -> None:
        # Bound discovery to this temporary hierarchy, independent of outer repos.
        root = self.work / "project"
        child = root / "import/cpu"
        nested = child / "rtl"
        nested.mkdir(parents=True)
        (root / "git_deps.toml").write_text("")
        self.assertEqual(mgr.locate_workspace(None, nested), (root, "git_deps.toml"))
        (child / "git_deps.toml").write_text("")
        with self.assertRaisesRegex(mgr.RepoMgrError, "multiple git_deps"):
            mgr.locate_workspace(None, nested)
        (root / ".git_repo").mkdir()
        (root / ".git_repo/resolved.toml").write_text("")
        self.assertEqual(mgr.locate_workspace(None, nested), (root, ".git_repo/resolved.toml"))
        (child / ".git_repo").mkdir()
        (child / ".git_repo/resolved.toml").write_text("")
        with self.assertRaisesRegex(mgr.RepoMgrError, "multiple .git_repo"):
            mgr.locate_workspace(None, nested)
        self.assertEqual(mgr.locate_workspace(str(child), nested), (child, "--workspace"))
        with self.assertRaises(mgr.RepoMgrError):
            mgr.locate_workspace(str(root / "absent"), nested)
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesRegex(mgr.RepoMgrError, "no workspace found"):
                mgr.locate_workspace(None, nested)
        with patch.object(mgr, "run_git", side_effect=AssertionError("show-root must not invoke Git")):
            code, output, error = self.invoke(["show-root", "--workspace", str(nested)])
        self.assertEqual((code, error), (0, ""))
        self.assertIn(str(nested), output)
        self.assertFalse((nested / ".git_repo").exists())

    def test_workspace_option_aliases(self) -> None:
        commands = [[name] for name in ("show-root", "sync", "status", "graph", "export-flat")]
        commands += [["forall", "-c", "git status"], ["switch", "main"], ["tag", "v1"]]
        commands += [["admin", name] for name in ("policy-status", "policy-diff", "policy-apply", "lock-main", "audit")]
        commands += [["admin", name, "main"] for name in ("protect", "unprotect")]
        commands += [["admin", name, "r1"] for name in ("unlock-main", "release", "release-resume")]
        for command in commands:
            for flag in ("--workspace", "-w"):
                with self.subTest(command=command, flag=flag):
                    args = mgr.parse_args([*command, flag, str(self.work)])
                    self.assertEqual(args.workspace_root, str(self.work))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            mgr.parse_args(["status", "--top", str(self.work)])
        code, output, error = self.invoke(["show-root", "-w", str(self.work)])
        self.assertEqual((code, error), (0, ""))
        self.assertIn(str(self.work), output)

    def test_sync_from_subdirectory(self) -> None:
        import os
        top = self.work / "plain"
        nested = top / "rtl/sub"
        nested.mkdir(parents=True)
        (top / "git_deps.toml").write_text("")
        previous = Path.cwd()
        try:
            os.chdir(nested)
            code, output, error = self.invoke(["sync"])
            self.assertEqual((code, error), (0, ""))
            self.assertIn(f"root_dir: {top} (git_deps.toml)", output)
            self.assertEqual(self.invoke(["status"])[0], 0)
            self.assertIn(".git_repo/resolved.toml", self.invoke(["show-root"])[1])
        finally:
            os.chdir(previous)
        self.assertTrue((top / ".git_repo/resolved.toml").is_file())
        self.assertFalse((nested / ".git_repo").exists())

    def test_plain_top_inside_parent_git_workspace(self) -> None:
        parent = self.create_repo("parent")
        leaf = self.create_repo("leaf")
        top = parent / "local_workspace"
        top.mkdir()
        (top / "git_deps.toml").write_text(self.dependency(leaf), encoding="utf-8")
        parent_commit = self.git(["rev-parse", "HEAD"], parent)
        code, _, error = self.invoke(["sync", "--workspace", str(top)])
        self.assertEqual((code, error), (0, ""))
        state = mgr.load_resolved(top)
        self.assertFalse(state["workspace"]["top_is_git"])
        self.assertEqual(state["workspace"]["top_commit"], "")
        self.assertEqual(state["workspace"]["top_repository"], "")
        self.assertEqual([name for name, _ in mgr.state_entries(top, state)], ["leaf"])
        self.assertEqual(self.invoke(["status", "--workspace", str(top)])[0], 0)
        self.assertIn("leaf", self.invoke(["graph", "--workspace", str(top), "--format", "tree"])[1])
        code, output, error = self.invoke(["forall", "--workspace", str(top), "-c", "git rev-parse --show-toplevel"])
        self.assertEqual((code, error), (0, ""))
        self.assertIn("==> leaf", output)
        self.assertNotIn("==> local_workspace", output)
        self.assertEqual(self.invoke(["switch", "main", "--workspace", str(top)])[0], 0)
        checkout = top / "import/leaf"
        self.git(["config", "user.name", "Test"], checkout)
        self.git(["config", "user.email", "test@example.com"], checkout)
        self.assertEqual(self.invoke(["tag", "plain-test", "--workspace", str(top)])[0], 0)
        self.assertEqual(self.git(["tag", "--list", "plain-test"], parent), "")
        self.assertEqual(self.git(["rev-parse", "HEAD"], parent), parent_commit)
        self.assertFalse((top / ".git").exists())
        snapshot = top / "snapshot.toml"
        self.assertEqual(self.invoke(["export-flat", "--workspace", str(top), "-o", str(snapshot)])[0], 0)
        restored = parent / "restored"
        restored.mkdir()
        self.assertEqual(self.invoke(["sync", "--workspace", str(restored), "--flat", str(snapshot)])[0], 0)
        self.assertEqual(self.invoke(["status", "--workspace", str(restored)])[0], 0)

    def test_empty_plain_top_and_git_worktree_detection(self) -> None:
        top = self.work / "empty"
        top.mkdir()
        (top / "git_deps.toml").write_text("", encoding="utf-8")
        self.assertEqual(self.invoke(["sync", "--workspace", str(top)])[0], 0)
        self.assertEqual(self.invoke(["status", "--workspace", str(top)])[0], 0)
        repo = self.create_repo("repo")
        worktree = self.work / "worktree"
        self.git(["worktree", "add", "--detach", str(worktree)], repo)
        self.assertTrue(mgr.is_git_root(worktree))
        (worktree / "subdir").mkdir()
        self.assertFalse(mgr.is_git_root(worktree / "subdir"))

    def test_template_without_git_and_no_overwrite(self) -> None:
        with patch.object(mgr, "run_git", side_effect=AssertionError("unexpected Git")):
            previous = Path.cwd()
            try:
                import os
                os.chdir(self.work)
                code, _, stderr = self.invoke(["template"])
            finally:
                os.chdir(previous)
            self.assertEqual((code, stderr), (0, ""))
            output = self.work / "git_deps.toml"
            original = output.read_bytes()
            self.assertEqual(mgr.parse_dependencies(tomllib.loads(original.decode()), output), ())
            code, _, stderr = self.invoke(["template", "-o", str(output)])
            self.assertEqual(code, 1)
            self.assertIn("E_OUTPUT_EXISTS", stderr)
            self.assertEqual(output.read_bytes(), original)
            custom = self.work / "nested/example.toml"
            self.assertEqual(self.invoke(["template", "-o", str(custom)])[0], 0)
            self.assertEqual(custom.read_bytes(), original)

    def test_missing_child_manifest_is_leaf(self) -> None:
        leaf = self.create_repo("leaf")
        self.git(["rm", "git_deps.toml"], leaf)
        self.git(["commit", "-q", "-m", "Remove optional leaf manifest"], leaf)
        empty = self.create_repo("empty")
        top = self.prepare_top(self.dependency(leaf) + self.dependency(empty))
        code, stdout, stderr = self.invoke(["sync", "--workspace", str(top)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("synced 2", stdout)
        self.assertFalse((top / "import/leaf/git_deps.toml").exists())
        self.assertTrue((top / "import/empty/git_deps.toml").is_file())
        self.assertTrue((top / ".git_repo/resolved.toml").is_file())
        (top / "git_deps.toml").unlink()
        self.assertIn("E_MANIFEST_MISSING", self.invoke(["sync", "--workspace", str(top)])[2])

    def test_invalid_child_manifest_still_fails(self) -> None:
        leaf = self.create_repo("invalid", "[broken")
        top = self.prepare_top(self.dependency(leaf))
        code, _, stderr = self.invoke(["sync", "--workspace", str(top)])
        self.assertEqual(code, 1)
        self.assertIn("E_TOML", stderr)
        self.assertFalse((top / ".git_repo/resolved.toml").exists())
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            with self.assertRaisesRegex(mgr.RepoMgrError, "failed to read"):
                mgr.read_toml(leaf / "git_deps.toml", "manifest", missing_ok=True)

    def test_sync_deduplicates_tree_and_exports_flat_snapshot(self) -> None:
        common = self.create_repo("common_ip")
        alu = self.create_repo("alu", self.dependency(common))
        lsu = self.create_repo("lsu")
        cpu = self.create_repo(
            "cpu",
            self.dependency(common) + self.dependency(alu) + self.dependency(lsu),
        )
        dma = self.create_repo("dma")
        npu = self.create_repo("npu", self.dependency(dma))
        top = self.prepare_top(
            self.dependency(common) + self.dependency(cpu) + self.dependency(npu),
        )

        code, stdout, stderr = self.invoke(["sync", "--workspace", str(top)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("synced 6 imported repository(s)", stdout)
        self.assertTrue((top / "import" / "common_ip" / ".git").exists())
        self.assertTrue((top / "import" / "alu" / ".git").exists())
        self.assertFalse((top / "import" / "cpu" / "import").exists())

        tree = (top / ".git_repo" / "tree.txt").read_text(encoding="utf-8")
        self.assertIn("├── common_ip", tree)
        self.assertIn("│   ├── common_ip [shared]", tree)
        self.assertIn("└── npu", tree)

        code, stdout, stderr = self.invoke(["status", "--workspace", str(top)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("Git Repository Status", stdout)
        self.assertIn("import/common_ip", stdout)
        self.assertIn("7 repositories", stdout)
        self.assertIn("7 clean", stdout)

        flat = top / "git_deps_flat.toml"
        code, _, stderr = self.invoke(["export-flat", "--workspace", str(top), "-o", str(flat)])
        self.assertEqual((code, stderr), (0, ""))
        snapshot = tomllib.loads(flat.read_text(encoding="utf-8"))
        self.assertEqual(len(snapshot["repository"]), 6)
        self.assertTrue(all(len(item["commit"]) == 40 for item in snapshot["repository"]))

    def test_status_table_and_details(self) -> None:
        common = self.create_repo("common")
        missing = self.create_repo("missing")
        top = self.prepare_top(self.dependency(common) + self.dependency(missing))
        self.assertEqual(self.invoke(["sync", "--workspace", str(top)])[0], 0)
        checkout = top / "import" / "common"
        self.git(["tag", "v1.2.0"], checkout)
        (checkout / "README.txt").write_text("modified\n", encoding="utf-8")
        (checkout / "new_note.md").write_text("note\n", encoding="utf-8")
        missing_checkout = top / "import" / "missing"
        original_is_dir = Path.is_dir
        with patch.object(Path, "is_dir", lambda path: False if path == missing_checkout else original_is_dir(path)):
            code, stdout, stderr = self.invoke(["status", "--workspace", str(top)])
        self.assertEqual((code, stderr), (1, ""))
        self.assertIn(f"Workspace: {top.as_posix()}", stdout)
        self.assertIn("v1.2.0", stdout)
        self.assertIn("3 repositories", stdout)
        for value in ("1 clean", "1 dirty", "1 missing", "DIRTY   import/common",
                      " M README.txt", "?? new_note.md", "MISSING import/missing",
                      f"Expected: {missing}", "Ref: main",
                      "HW Tool: Sync Git Repositories..."):
            self.assertIn(value, stdout)
        original_is_git_root = mgr.is_git_root
        with patch.object(mgr, "is_git_root", side_effect=lambda path: False if path == missing_checkout else original_is_git_root(path)):
            code, stdout, _ = self.invoke(["status", "--workspace", str(top)])
        self.assertEqual(code, 1)
        self.assertIn("ERROR   import/missing", stdout)
        self.assertIn("1 error", stdout)

    def test_normalizes_ssh_and_http_repository_urls(self) -> None:
        expected = "remote:git.example.com/dmg/common_ip"
        repositories = (
            "git@git.example.com:dmg/common_ip.git",
            "ssh://git@git.example.com/dmg/common_ip.git",
            "https://git.example.com/dmg/common_ip.git",
            "http://git.example.com/dmg/common_ip/",
        )

        self.assertEqual({mgr.normalize_repository(repository) for repository in repositories}, {expected})
        self.assertNotEqual(
            mgr.normalize_repository("https://mirror.example.com/dmg/common_ip.git"),
            expected,
        )

    def test_normalizes_file_url_and_absolute_path(self) -> None:
        common = self.create_repo("common_ip")
        top = self.prepare_top(self.dependency(common.as_uri()) + self.dependency(common))

        self.assertEqual(mgr.normalize_repository(common.as_uri()), mgr.normalize_repository(str(common)))

        code, stdout, stderr = self.invoke(["sync", "--workspace", str(top)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("synced 1 imported repository(s)", stdout)
        self.assertEqual(len(list((top / "import").iterdir())), 1)

    def test_reports_ref_conflict_with_dependency_paths(self) -> None:
        common = self.create_repo("common_ip")
        self.git(["tag", "v1.0"], common)
        cpu = self.create_repo("cpu", self.dependency(common, "main"))
        npu = self.create_repo("npu", self.dependency(common, "v1.0"))
        top = self.prepare_top(self.dependency(cpu) + self.dependency(npu))

        code, _, stderr = self.invoke(["sync", "--workspace", str(top)])
        self.assertEqual(code, 1)
        self.assertIn("ERROR [E_REF_CONFLICT]", stderr)
        self.assertIn("top -> cpu -> common_ip  ref: main", stderr)
        self.assertIn("top -> npu -> common_ip  ref: v1.0", stderr)

    def test_reports_recursive_dependency_cycle(self) -> None:
        cpu = self.create_repo("cpu")
        alu = self.create_repo("alu", self.dependency(cpu))
        (cpu / "git_deps.toml").write_text(self.dependency(alu), encoding="utf-8")
        self.git(["add", "git_deps.toml"], cpu)
        self.git(["commit", "-q", "-m", "add alu dependency"], cpu)
        top = self.prepare_top(self.dependency(cpu))

        code, _, stderr = self.invoke(["sync", "--workspace", str(top)])
        self.assertEqual(code, 1)
        self.assertIn("ERROR [E_DEPENDENCY_CYCLE]", stderr)
        self.assertIn("cycle: cpu -> alu -> cpu", stderr)

    def test_requires_explicit_checkout_name_for_basename_collision(self) -> None:
        common_a = self.create_repo("a/common_ip")
        common_b = self.create_repo("b/common_ip")
        top = self.prepare_top(self.dependency(common_a) + self.dependency(common_b))

        code, _, stderr = self.invoke(["sync", "--workspace", str(top)])
        self.assertEqual(code, 1)
        self.assertIn("ERROR [E_CHECKOUT_NAME_CONFLICT]", stderr)
        self.assertIn("add a unique [[checkout]] name", stderr)

    def test_top_checkout_override_resolves_basename_collision(self) -> None:
        common_a = self.create_repo("a/common_ip")
        common_b = self.create_repo("b/common_ip")
        manifest = (
            self.dependency(common_a)
            + self.dependency(common_b)
            + "\n[[checkout]]\n"
            + f"repository = {json.dumps(str(common_b))}\n"
            + 'name = "vendor_common_ip"\n'
        )
        top = self.prepare_top(manifest)

        code, _, stderr = self.invoke(["sync", "--workspace", str(top)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertTrue((top / "import" / "common_ip").is_dir())
        self.assertTrue((top / "import" / "vendor_common_ip").is_dir())

    def test_flat_snapshot_restores_a_new_top_checkout(self) -> None:
        common = self.create_repo("common_ip")
        top = self.prepare_top(self.dependency(common))
        code, _, stderr = self.invoke(["sync", "--workspace", str(top)])
        self.assertEqual((code, stderr), (0, ""))
        flat = top / "git_deps_flat.toml"
        code, _, stderr = self.invoke(["export-flat", "--workspace", str(top), "-o", str(flat)])
        self.assertEqual((code, stderr), (0, ""))

        restored = self.work / "restored_top"
        subprocess.run(["git", "clone", "-q", str(top), str(restored)], check=True)
        code, _, stderr = self.invoke(
            ["sync", "--workspace", str(restored), "--flat", str(flat)],
        )
        self.assertEqual((code, stderr), (0, ""))
        self.assertTrue((restored / "import" / "common_ip" / ".git").exists())

    def test_switch_dry_run_and_tag_cover_every_checkout(self) -> None:
        common = self.create_repo("common_ip")
        top = self.prepare_top(self.dependency(common))
        code, _, stderr = self.invoke(["sync", "--workspace", str(top)])
        self.assertEqual((code, stderr), (0, ""))

        code, stdout, stderr = self.invoke(["switch", "main", "--workspace", str(top), "--dry-run"])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("[plan] top: switch to main", stdout)
        self.assertIn("[plan] common_ip: switch to main", stdout)

        code, _, stderr = self.invoke(["tag", "integration_r1", "--workspace", str(top)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(self.git(["tag", "--list", "integration_r1"], top), "integration_r1")
        self.assertEqual(
            self.git(["tag", "--list", "integration_r1"], top / "import" / "common_ip"),
            "integration_r1",
        )

    def test_forall_runs_in_selected_checkout_and_supports_dry_run(self) -> None:
        common = self.create_repo("common_ip")
        top = self.prepare_top(self.dependency(common))
        code, _, stderr = self.invoke(["sync", "--workspace", str(top)])
        self.assertEqual((code, stderr), (0, ""))

        code, stdout, stderr = self.invoke(
            ["forall", "-c", "git rev-parse --show-prefix", "common_ip", "--workspace", str(top)],
        )
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("==> common_ip (import/common_ip)", stdout)
        self.assertNotIn("==> top (.)", stdout)

        code, stdout, stderr = self.invoke(
            ["forall", "-c", "git status --short", "--workspace", str(top), "--dry-run"],
        )
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("[plan] top (.): git status --short", stdout)
        self.assertIn("[plan] common_ip (import/common_ip): git status --short", stdout)

    def test_admin_policy_lock_release_resume_and_audit(self) -> None:
        FakeProviderClient.applied = []
        FakeProviderClient.restored = []
        common = self.create_repo("common_ip")
        top = self.prepare_top(self.dependency(common))
        code, _, stderr = self.invoke(["sync", "--workspace", str(top)])
        self.assertEqual((code, stderr), (0, ""))

        state_path = top / ".git_repo" / "resolved.toml"
        state = tomllib.loads(state_path.read_text(encoding="utf-8"))
        state["workspace"]["top_repository"] = "https://github.example/company/top.git"
        state["repository"][0]["repository"] = "https://github.example/company/common_ip.git"
        state_path.write_text(mgr.state_to_toml({"workspace": state["workspace"], "repositories": state["repository"]}), encoding="utf-8")

        config = top / "git_repo_admin.toml"
        config.write_text(
            "[policy]\n"
            "branch = \"main\"\n"
            "baseline_mode = \"integration-only\"\n\n"
            "[[provider]]\n"
            "name = \"github\"\n"
            "type = \"github\"\n"
            "host = \"github.example\"\n"
            "api_url = \"https://api.github.example\"\n"
            "token_env = \"GIT_REPO_TEST_TOKEN\"\n"
            "github_users = [\"release-bot\"]\n",
            encoding="utf-8",
        )
        self.git(["add", "git_repo_admin.toml"], top)
        self.git(["commit", "-q", "-m", "add admin config"], top)

        with patch.dict("os.environ", {"GIT_REPO_TEST_TOKEN": "token"}), patch.object(
            mgr,
            "provider_client",
            side_effect=lambda provider: FakeProviderClient(provider),
        ):
            code, stdout, stderr = self.invoke(["admin", "policy-status", "--workspace", str(top)])
            self.assertEqual((code, stderr), (0, ""))
            self.assertIn("[provider] github: github as release-bot", stdout)
            self.assertIn("[ok] top: github main integration-only", stdout)

            code, _, stderr = self.invoke(["admin", "policy-diff", "--workspace", str(top)])
            self.assertEqual((code, stderr), (0, ""))

            code, stdout, stderr = self.invoke(
                ["admin", "protect", "main", "--workspace", str(top)],
            )
            self.assertEqual((code, stderr), (0, ""))
            self.assertIn("top: main -> integration-only", stdout)
            self.assertEqual(len(FakeProviderClient.applied), 2)

            code, stdout, stderr = self.invoke(
                ["admin", "unprotect", "main", "--workspace", str(top)],
            )
            self.assertEqual((code, stderr), (0, ""))
            self.assertIn("top: removed main protection", stdout)
            self.assertEqual(len(FakeProviderClient.restored), 2)

            code, stdout, stderr = self.invoke(
                ["admin", "lock-main", "--workspace", str(top), "--lock-id", "test_lock"],
            )
            self.assertEqual((code, stderr), (0, ""))
            self.assertIn("lock_id: test_lock", stdout)
            self.assertEqual(len(FakeProviderClient.applied), 4)
            self.assertTrue((top / ".git_repo" / "admin" / "locks" / "test_lock.json").is_file())

            code, _, stderr = self.invoke(["admin", "unlock-main", "test_lock", "--workspace", str(top)])
            self.assertEqual((code, stderr), (0, ""))
            self.assertEqual(len(FakeProviderClient.restored), 4)

            code, _, stderr = self.invoke(["admin", "release", "release_r1", "--workspace", str(top)])
            self.assertEqual((code, stderr), (0, ""))
            self.assertTrue((top / ".git_repo" / "admin" / "releases" / "release_r1.json").is_file())
            self.assertEqual(self.git(["tag", "--list", "release_r1"], top), "release_r1")

            code, _, stderr = self.invoke(["admin", "release-resume", "release_r1", "--workspace", str(top)])
            self.assertEqual((code, stderr), (0, ""))
            code, stdout, stderr = self.invoke(["admin", "audit", "--workspace", str(top)])
            self.assertEqual((code, stderr), (0, ""))
            self.assertIn('"operation": "release"', stdout)


if __name__ == "__main__":
    unittest.main()
