from __future__ import annotations

import subprocess
import sys
import tempfile
import tomllib
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


PUBLISH_ROOT = Path(__file__).resolve().parents[1] / "publish"
sys.path.insert(0, str(PUBLISH_ROOT))

from build_release import (
    PY_TOOLS_PATHS,
    REPOSITORY_MAP,
    build_release,
    clone_repository,
    parse_named_values,
    resolve_external_repository,
    validate_release_sources,
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


def initialize_repository(root: Path) -> None:
    root.mkdir(parents=True)
    run_git(root, "init", "--quiet", "--initial-branch=main")
    run_git(root, "config", "user.email", "release-test@example.com")
    run_git(root, "config", "user.name", "Release Test")


def commit_repository(root: Path, tag: str | None = None) -> str:
    run_git(root, "add", ".")
    run_git(root, "commit", "--quiet", "-m", "initial")
    if tag is not None:
        run_git(root, "tag", tag)
    return run_git(root, "rev-parse", "HEAD")


def create_source_repository(root: Path, tag: str | None = None) -> str:
    initialize_repository(root)
    (root / "README.md").write_text("# source\n", encoding="utf-8")
    return commit_repository(root, tag)


def create_py_tools_repository(root: Path, tag: str) -> str:
    initialize_repository(root)
    hw_tool = root / "hw_tool"
    registry = hw_tool / "hw_tool_de" / "src" / "tool_registry.py"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        "from dataclasses import dataclass\n\n"
        "@dataclass(frozen=True)\n"
        "class RepositorySpec:\n"
        "    name: str\n"
        "    repository: str\n"
        "    branch: str\n"
        "    checkout: str\n"
        "    workspace: str | None = None\n\n"
        "REPOSITORY_MAP = {}\n",
        encoding="utf-8",
    )
    (hw_tool / "TAGGED_SOURCE.txt").write_text(
        "source from selected tag\n",
        encoding="utf-8",
    )
    for relative_path in PY_TOOLS_PATHS:
        tool_root = root / relative_path
        tool_root.mkdir(parents=True)
        (tool_root / "README.md").write_text(
            f"# {relative_path}\n",
            encoding="utf-8",
        )
    return commit_repository(root, tag)


class ReleaseTest(unittest.TestCase):
    def test_parse_named_values(self) -> None:
        self.assertEqual(
            parse_named_values(
                ["py_tools_for_hw=v1.1.1"],
                "--repo-ref",
            ),
            {"py_tools_for_hw": "v1.1.1"},
        )
        with self.assertRaisesRegex(ValueError, "unknown repository"):
            parse_named_values(["com=main"], "--repo-ref")

    def test_official_release_requires_py_tools_ref(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires --repo-ref for: py_tools_for_hw"):
            validate_release_sources(
                True,
                {},
            )
        validate_release_sources(True, {"py_tools_for_hw": "v1.0.0"})

    def test_development_release_keeps_py_tools_workspace(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires --official"):
            validate_release_sources(
                False,
                {"py_tools_for_hw": "v1.0.0"},
            )

    def test_clone_repository_full_and_shallow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            source = temporary_root / "source"
            commit = create_source_repository(source)
            for shallow in (False, True):
                destination = temporary_root / f"clone_{shallow}"
                clone_repository(source.as_uri(), "main", destination, shallow)
                self.assertEqual(run_git(destination, "rev-parse", "HEAD"), commit)

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
            output_root = temporary_root / "out"
            tool_root, archive = build_release(
                "1.1.1",
                output_root,
                create_archive=False,
            )

            self.assertIsNone(archive)
            mem_tool_readme = (
                tool_root
                / "repository"
                / "py_tools_for_hw"
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
            self.assertFalse(metadata["release"]["official"])
            self.assertEqual(
                metadata["repository"]["py_tools_for_hw"]["source"],
                "workspace",
            )
            self.assertNotIn("com", metadata["repository"])

    def test_official_release_clones_selected_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            py_tools_source = temporary_root / "py_tools_for_hw"
            py_tools_commit = create_py_tools_repository(
                py_tools_source,
                "v1.0.0",
            )
            py_tools_spec = replace(
                REPOSITORY_MAP["py_tools_for_hw"],
                repository=py_tools_source.as_uri(),
            )

            with patch.dict(
                REPOSITORY_MAP,
                {"py_tools_for_hw": py_tools_spec},
            ):
                tool_root, archive = build_release(
                    "1.0.0",
                    temporary_root / "out",
                    create_archive=False,
                    repository_refs={
                        "py_tools_for_hw": "v1.0.0",
                    },
                    official=True,
                )

            self.assertIsNone(archive)
            self.assertTrue((tool_root / "TAGGED_SOURCE.txt").is_file())
            metadata = tomllib.loads(
                (tool_root / "release_info.toml").read_text(encoding="utf-8")
            )
            self.assertTrue(metadata["release"]["official"])
            self.assertEqual(
                metadata["repository"]["py_tools_for_hw"]["commit"],
                py_tools_commit,
            )
            self.assertEqual(
                metadata["repository"]["py_tools_for_hw"]["ref_kind"],
                "tag",
            )
            self.assertNotIn("com", metadata["repository"])

    def test_official_release_rejects_branch_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "py_tools_for_hw"
            initialize_repository(source)
            (source / "README.md").write_text("# source\n", encoding="utf-8")
            commit_repository(source)
            spec = replace(
                REPOSITORY_MAP["py_tools_for_hw"],
                repository=source.as_uri(),
            )
            with self.assertRaisesRegex(ValueError, "existing tag or full"):
                with resolve_external_repository(
                    spec,
                    "main",
                    None,
                    shallow=False,
                    require_immutable_ref=True,
                ):
                    pass


if __name__ == "__main__":
    unittest.main()
