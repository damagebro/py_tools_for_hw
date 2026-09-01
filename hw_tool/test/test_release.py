from __future__ import annotations

import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


PUBLISH_ROOT = Path(__file__).resolve().parents[1] / "publish"
sys.path.insert(0, str(PUBLISH_ROOT))

from build_release import (
    REPOSITORY_MAP,
    build_release,
    clone_repository,
    parse_named_values,
    resolve_external_repository,
    write_linux_modulefile,
)


def run_git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def create_com_repository(root: Path) -> str:
    root.mkdir(parents=True)
    run_git(root, "init", "--quiet", "--initial-branch=main")
    run_git(root, "config", "user.email", "release-test@example.com")
    run_git(root, "config", "user.name", "Release Test")
    mem_tool = root / "impl_template" / "memory" / "mem_tool"
    mem_tool.mkdir(parents=True)
    (mem_tool / "README.md").write_text("# mem_tool\n", encoding="utf-8")
    run_git(root, "add", ".")
    run_git(root, "commit", "--quiet", "-m", "initial")
    return run_git(root, "rev-parse", "HEAD")


class ReleaseTest(unittest.TestCase):
    def test_parse_named_values(self) -> None:
        self.assertEqual(
            parse_named_values(["com=v1.1.1"], "--repo-ref"),
            {"com": "v1.1.1"},
        )
        with self.assertRaisesRegex(ValueError, "unknown repository"):
            parse_named_values(["unknown=main"], "--repo-ref")

    def test_clone_repository_full_and_shallow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            source = temporary_root / "source"
            commit = create_com_repository(source)
            for shallow in (False, True):
                destination = temporary_root / f"clone_{shallow}"
                clone_repository(source.as_uri(), "main", destination, shallow)
                self.assertEqual(run_git(destination, "rev-parse", "HEAD"), commit)

    def test_local_path_takes_precedence_over_repository_url(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source"
            commit = create_com_repository(source)
            with resolve_external_repository(
                REPOSITORY_MAP["com"],
                "main",
                source,
                shallow=False,
            ) as repository:
                self.assertEqual(repository.source, "path")
                self.assertEqual(repository.root, source.resolve())
                self.assertEqual(repository.ref, "working-tree")
                self.assertEqual(repository.commit, commit)

    def test_modulefile_uses_requested_version_and_install_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            release_root = Path(temporary_directory)
            modulefile = write_linux_modulefile(
                release_root,
                "1.1.1",
                "/opt/company/hw_tool",
            )
            content = modulefile.read_text(encoding="utf-8")
            self.assertEqual(modulefile.name, "1.1.1")
            self.assertIn("/opt/company/hw_tool/1.1.1/hw_tool", content)
            self.assertIn("HW_TOOL_VERSION 1.1.1", content)
            self.assertNotIn("0.1.0", content)

    def test_build_release_records_sources_and_generates_modulefile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            source = temporary_root / "com"
            commit = create_com_repository(source)
            output_root = temporary_root / "out"
            tool_root, archive = build_release(
                "1.1.1",
                output_root,
                create_archive=False,
                repository_paths={"com": source},
            )

            self.assertIsNone(archive)
            mem_tool_readme = (
                tool_root
                / "repository"
                / "com"
                / "impl_template"
                / "memory"
                / "mem_tool"
                / "README.md"
            )
            self.assertTrue(mem_tool_readme.is_file())
            modulefile = tool_root.parent / "modulefiles" / "hw_tool" / "1.1.1"
            self.assertTrue(modulefile.is_file())
            metadata = tomllib.loads(
                (tool_root / "release_info.toml").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["release"]["version"], "1.1.1")
            self.assertEqual(metadata["repository"]["com"]["source"], "path")
            self.assertEqual(metadata["repository"]["com"]["ref"], "working-tree")
            self.assertEqual(metadata["repository"]["com"]["commit"], commit)


if __name__ == "__main__":
    unittest.main()
