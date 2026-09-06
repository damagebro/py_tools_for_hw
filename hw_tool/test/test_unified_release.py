from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

PUBLISH = Path(__file__).resolve().parents[1] / "publish"
sys.path.insert(0, str(PUBLISH))
sys.path.insert(0, str(Path(__file__).parent))

import build_release as builder
from release import publish
from verify_release import digest, verify_release, write_checksums
from test_release import initialize_repository, commit_repository, run_git


class UnifiedReleaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.bundle = publish("2.3.4-test.1", cls.root / "out")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_artifacts_share_version_and_runtime(self):
        metadata = verify_release(self.bundle)
        self.assertEqual(metadata["release"]["version"], "2.3.4-test.1")
        repository = metadata["repository"]["py_tools_for_hw"]
        self.assertEqual(repository["branch"], run_git(builder.SOURCE_ROOT, "branch", "--show-current"))
        self.assertEqual(repository["tag"], "")
        verify_release(self.bundle / "hw_tool")
        with ZipFile(self.bundle / "hw_tool-2.3.4-test.1.zip") as archive:
            entry = archive.getinfo("hw_tool/bin/hw_tool")
            self.assertEqual(entry.create_system, 3)
            self.assertEqual(entry.external_attr >> 16 & 0o777, 0o755)
            self.assertNotIn(b"\r\n", archive.read(entry))
        with ZipFile(self.bundle / "dmg-hw-tool-2.3.4-test.1.vsix") as archive:
            self.assertEqual(json.loads(archive.read("extension/package.json"))["version"], "2.3.4-test.1")
            self.assertEqual(archive.read("extension/runtime/hw_tool/release_info.toml"),
                             (self.bundle / "hw_tool/release_info.toml").read_bytes())

    def test_existing_output_is_unchanged(self):
        before = digest(self.bundle / "SHA256SUMS")
        with self.assertRaisesRegex(FileExistsError, "already exists"):
            publish("2.3.4-test.1", self.bundle.parent)
        self.assertEqual(digest(self.bundle / "SHA256SUMS"), before)
        verify_release(self.bundle)

    def test_offline_doctor_accepts_source_release(self):
        result = subprocess.run([sys.executable, "-B", str(self.bundle / "hw_tool/src/hw_tool.py"), "doctor"],
                                cwd=self.bundle, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("not a git checkout", result.stdout)

    def test_failed_build_never_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("release.prepare_extension", side_effect=ValueError("snippet failed")):
                with self.assertRaisesRegex(ValueError, "snippet failed"):
                    publish("2.3.5", Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])
            with patch("release.verify_release", side_effect=ValueError("verification failed")):
                with self.assertRaisesRegex(ValueError, "verification failed"):
                    publish("2.3.5", Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_invalid_versions_and_concurrent_build(self):
        for value in ("../escape", "1.0", "01.2.3", "1.2.3\n", "1.2.3+abc", "1.2.3-a/../../b"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                builder.validate_version(value)
        with tempfile.TemporaryDirectory() as directory:
            with builder.release_staging(Path(directory), "1.2.3"):
                with self.assertRaises(FileExistsError):
                    publish("1.2.3", Path(directory))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                builder.write_linux_modulefile(Path(directory), "1.2.3", "/tools/{bad}")

    def test_checksum_detects_changed_missing_extra_files(self):
        for change in ("modified", "missing", "extra"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                installed = Path(directory) / "hw_tool"
                shutil.copytree(self.bundle / "hw_tool", installed)
                target = installed / "README.md"
                if change == "modified":
                    target.write_text("changed", encoding="utf-8")
                elif change == "missing":
                    target.unlink()
                else:
                    (installed / "unexpected.py").write_text("", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "SHA256|inventory"):
                    verify_release(installed)

    def test_archive_cross_check(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bundle"
            shutil.copytree(self.bundle, bundle)
            (bundle / "hw_tool/README.md").write_text("different from ZIP and VSIX", encoding="utf-8")
            write_checksums(bundle / "hw_tool")
            write_checksums(bundle)
            with self.assertRaisesRegex(ValueError, "archive runtime content"):
                verify_release(bundle)

    def test_official_tag_and_commit_use_only_selected_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            initialize_repository(source)
            shutil.copytree(builder.HW_TOOL_ROOT, source / "hw_tool",
                            ignore=builder.make_hw_tool_copy_ignore(builder.HW_TOOL_ROOT))
            for relative in builder.PY_TOOLS_PATHS:
                builder.copy_tree(builder.SOURCE_ROOT / relative, source / relative)
            commit = commit_repository(source, "v7.8.9")
            run_git(source, "branch", "v7.8.9")
            (source / "hw_tool/publish/vscode/src/extension.js").write_text("UNCOMMITTED", encoding="utf-8")
            (source / "py_rtl_snippet/input/rtl_snippets.md").write_text("INVALID", encoding="utf-8")
            spec = replace(builder.REPOSITORY_MAP["py_tools_for_hw"], repository=source.as_uri())
            with patch.dict(builder.REPOSITORY_MAP, {"py_tools_for_hw": spec}):
                for index, ref in enumerate(("v7.8.9", commit)):
                    with patch("build_release.clone_repository", wraps=builder.clone_repository) as clone:
                        bundle = publish(f"7.8.{9 + index}", root / "out", official=True,
                                         repository_refs={"py_tools_for_hw": ref}, shallow=bool(index))
                        self.assertEqual(clone.call_count, 1)
                    metadata = verify_release(bundle)["repository"]["py_tools_for_hw"]
                    self.assertEqual(metadata["commit"], commit)
                    self.assertFalse(metadata["dirty"])
                    self.assertEqual(metadata["branch"], "")
                    self.assertEqual(metadata["tag"], "v7.8.9" if index == 0 else "")
                    self.assertNotIn("UNCOMMITTED", (bundle / "hw_tool/publish/vscode/src/extension.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
