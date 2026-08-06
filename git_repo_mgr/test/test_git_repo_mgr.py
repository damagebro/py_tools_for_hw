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

        code, stdout, stderr = self.invoke(["sync", "--top", str(top)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("synced 6 imported repository(s)", stdout)
        self.assertTrue((top / "import" / "common_ip" / ".git").exists())
        self.assertTrue((top / "import" / "alu" / ".git").exists())
        self.assertFalse((top / "import" / "cpu" / "import").exists())

        tree = (top / ".git_repo" / "tree.txt").read_text(encoding="utf-8")
        self.assertIn("├── common_ip", tree)
        self.assertIn("│   ├── common_ip [shared]", tree)
        self.assertIn("└── npu", tree)

        code, stdout, stderr = self.invoke(["status", "--top", str(top)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("[ok] top:", stdout)
        self.assertIn("[ok] common_ip:", stdout)

        flat = top / "git_deps_flat.toml"
        code, _, stderr = self.invoke(["export-flat", "--top", str(top), "-o", str(flat)])
        self.assertEqual((code, stderr), (0, ""))
        snapshot = tomllib.loads(flat.read_text(encoding="utf-8"))
        self.assertEqual(len(snapshot["repository"]), 6)
        self.assertTrue(all(len(item["commit"]) == 40 for item in snapshot["repository"]))

    def test_reports_ref_conflict_with_dependency_paths(self) -> None:
        common = self.create_repo("common_ip")
        self.git(["tag", "v1.0"], common)
        cpu = self.create_repo("cpu", self.dependency(common, "main"))
        npu = self.create_repo("npu", self.dependency(common, "v1.0"))
        top = self.prepare_top(self.dependency(cpu) + self.dependency(npu))

        code, _, stderr = self.invoke(["sync", "--top", str(top)])
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

        code, _, stderr = self.invoke(["sync", "--top", str(top)])
        self.assertEqual(code, 1)
        self.assertIn("ERROR [E_DEPENDENCY_CYCLE]", stderr)
        self.assertIn("cycle: cpu -> alu -> cpu", stderr)

    def test_requires_explicit_checkout_name_for_basename_collision(self) -> None:
        common_a = self.create_repo("a/common_ip")
        common_b = self.create_repo("b/common_ip")
        top = self.prepare_top(self.dependency(common_a) + self.dependency(common_b))

        code, _, stderr = self.invoke(["sync", "--top", str(top)])
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

        code, _, stderr = self.invoke(["sync", "--top", str(top)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertTrue((top / "import" / "common_ip").is_dir())
        self.assertTrue((top / "import" / "vendor_common_ip").is_dir())

    def test_flat_snapshot_restores_a_new_top_checkout(self) -> None:
        common = self.create_repo("common_ip")
        top = self.prepare_top(self.dependency(common))
        code, _, stderr = self.invoke(["sync", "--top", str(top)])
        self.assertEqual((code, stderr), (0, ""))
        flat = top / "git_deps_flat.toml"
        code, _, stderr = self.invoke(["export-flat", "--top", str(top), "-o", str(flat)])
        self.assertEqual((code, stderr), (0, ""))

        restored = self.work / "restored_top"
        subprocess.run(["git", "clone", "-q", str(top), str(restored)], check=True)
        code, _, stderr = self.invoke(
            ["sync", "--top", str(restored), "--flat", str(flat)],
        )
        self.assertEqual((code, stderr), (0, ""))
        self.assertTrue((restored / "import" / "common_ip" / ".git").exists())

    def test_switch_dry_run_and_tag_cover_every_checkout(self) -> None:
        common = self.create_repo("common_ip")
        top = self.prepare_top(self.dependency(common))
        code, _, stderr = self.invoke(["sync", "--top", str(top)])
        self.assertEqual((code, stderr), (0, ""))

        code, stdout, stderr = self.invoke(["switch", "main", "--top", str(top), "--dry-run"])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("[plan] top: switch to main", stdout)
        self.assertIn("[plan] common_ip: switch to main", stdout)

        code, _, stderr = self.invoke(["tag", "integration_r1", "--top", str(top)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(self.git(["tag", "--list", "integration_r1"], top), "integration_r1")
        self.assertEqual(
            self.git(["tag", "--list", "integration_r1"], top / "import" / "common_ip"),
            "integration_r1",
        )

    def test_forall_runs_in_selected_checkout_and_supports_dry_run(self) -> None:
        common = self.create_repo("common_ip")
        top = self.prepare_top(self.dependency(common))
        code, _, stderr = self.invoke(["sync", "--top", str(top)])
        self.assertEqual((code, stderr), (0, ""))

        code, stdout, stderr = self.invoke(
            ["forall", "-c", "git rev-parse --show-prefix", "common_ip", "--top", str(top)],
        )
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("==> common_ip (import/common_ip)", stdout)
        self.assertNotIn("==> top (.)", stdout)

        code, stdout, stderr = self.invoke(
            ["forall", "-c", "git status --short", "--top", str(top), "--dry-run"],
        )
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("[plan] top (.): git status --short", stdout)
        self.assertIn("[plan] common_ip (import/common_ip): git status --short", stdout)

    def test_admin_policy_lock_release_resume_and_audit(self) -> None:
        FakeProviderClient.applied = []
        FakeProviderClient.restored = []
        common = self.create_repo("common_ip")
        top = self.prepare_top(self.dependency(common))
        code, _, stderr = self.invoke(["sync", "--top", str(top)])
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
            code, stdout, stderr = self.invoke(["admin", "policy-status", "--top", str(top)])
            self.assertEqual((code, stderr), (0, ""))
            self.assertIn("[provider] github: github as release-bot", stdout)
            self.assertIn("[ok] top: github main integration-only", stdout)

            code, _, stderr = self.invoke(["admin", "policy-diff", "--top", str(top)])
            self.assertEqual((code, stderr), (0, ""))

            code, stdout, stderr = self.invoke(
                ["admin", "protect", "main", "--top", str(top)],
            )
            self.assertEqual((code, stderr), (0, ""))
            self.assertIn("top: main -> integration-only", stdout)
            self.assertEqual(len(FakeProviderClient.applied), 2)

            code, stdout, stderr = self.invoke(
                ["admin", "unprotect", "main", "--top", str(top)],
            )
            self.assertEqual((code, stderr), (0, ""))
            self.assertIn("top: removed main protection", stdout)
            self.assertEqual(len(FakeProviderClient.restored), 2)

            code, stdout, stderr = self.invoke(
                ["admin", "lock-main", "--top", str(top), "--lock-id", "test_lock"],
            )
            self.assertEqual((code, stderr), (0, ""))
            self.assertIn("lock_id: test_lock", stdout)
            self.assertEqual(len(FakeProviderClient.applied), 4)
            self.assertTrue((top / ".git_repo" / "admin" / "locks" / "test_lock.json").is_file())

            code, _, stderr = self.invoke(["admin", "unlock-main", "test_lock", "--top", str(top)])
            self.assertEqual((code, stderr), (0, ""))
            self.assertEqual(len(FakeProviderClient.restored), 4)

            code, _, stderr = self.invoke(["admin", "release", "release_r1", "--top", str(top)])
            self.assertEqual((code, stderr), (0, ""))
            self.assertTrue((top / ".git_repo" / "admin" / "releases" / "release_r1.json").is_file())
            self.assertEqual(self.git(["tag", "--list", "release_r1"], top), "release_r1")

            code, _, stderr = self.invoke(["admin", "release-resume", "release_r1", "--top", str(top)])
            self.assertEqual((code, stderr), (0, ""))
            code, stdout, stderr = self.invoke(["admin", "audit", "--top", str(top)])
            self.assertEqual((code, stderr), (0, ""))
            self.assertIn('"operation": "release"', stdout)


if __name__ == "__main__":
    unittest.main()
