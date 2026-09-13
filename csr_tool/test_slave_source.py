import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from src.autogen_reg import build_argument_parser, main
from src.reg_common import CSRValidationError, parse_special
from src.reg_gen_doc import DocGenerator
from src.reg_parser import CSRParser
from src.slave_source import SlaveSources, parse_base_sources, source_rows


HEADER = "# reg_define\n\n| offset | reg_name | field | msb | lsb | SW_access | default_value | reg_type | special | description |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
LEAF = HEADER + "| 0 | cfg0 | data | 31 | 0 | RW | 1 | cfg | - | |\n"


def with_base(text, rows):
    base = "# base_info\n\n| item | type_input |\n| --- | --- |\n"
    return base + "".join(f"| {key} | {value} |\n" for key, value in rows) + "\n" + text


def slave(path, filename, rows=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(with_base(HEADER + f"| 0 | sub | | | | | | slave | slv_filename={filename}, bytesize=0x100 | |\n", rows), encoding="utf-8")


class SlaveSourceTests(unittest.TestCase):
    def test_ignore_missing_recursive_slave_preserves_window_and_siblings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            top = root / "top.md"
            slave(top, "child.md")
            child = root / "child.md"
            child.write_text(HEADER +
                "| 0 | missing | | | | | | slave | slv_filename=missing.md, bytesize=0x40 | |\n" +
                "| 0x40 | found | | | | | | slave | slv_filename=leaf.md, bytesize=0x40 | |\n",
                encoding="utf-8")
            (root / "leaf.md").write_text(LEAF, encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                CSRParser(str(top), nested=True).parse()
            warnings = io.StringIO()
            with contextlib.redirect_stderr(warnings):
                module = CSRParser(str(top), nested=True, slv_ignore=True).parse()
            node = module.sub_modules[0].module_obj
            self.assertEqual(len(node.registers), 2)
            self.assertEqual(node.registers[0].special.bytesize, 0x40)
            self.assertEqual([sub.instance_name for sub in node.sub_modules], ["found"])
            self.assertIn("missing.md", warnings.getvalue())
            self.assertIn(str(child), warnings.getvalue())
            self.assertIn("[WARNING]", warnings.getvalue())
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["-i", str(top), "--nested", "--slv_ignore", "-o", str(root / "out")]), 0)
            self.assertTrue(any((root / "out" / "rtl").glob("*.sv")))

    def test_ignore_missing_does_not_hide_other_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            top = root / "top.md"
            slave(top, "missing.md", [("slave_dir", str(root / "absent"))])
            with self.assertRaisesRegex(CSRValidationError, "directory not found"):
                CSRParser(str(top), nested=True, slv_ignore=True).parse()
            slave(top, "child.md", [("slave_dir", str(root / "library"))])
            for name in ("a", "b"):
                folder = root / "library" / name
                folder.mkdir(parents=True)
                (folder / "child.md").write_text(LEAF, encoding="utf-8")
            with self.assertRaisesRegex(CSRValidationError, "ambiguous"):
                CSRParser(str(top), nested=True, slv_ignore=True).parse()
            slave(top, "child.md", [("slave_git", "url=https://example/repo.git")])
            with patch.object(SlaveSources, "checkout", side_effect=CSRValidationError("Git slave download failed")):
                with self.assertRaisesRegex(CSRValidationError, "download failed"):
                    CSRParser(str(top), nested=True, slv_ignore=True).parse()
            (root / "child.md").write_text("invalid document", encoding="utf-8")
            with self.assertRaises(CSRValidationError):
                CSRParser(str(top), nested=True, slv_ignore=True).parse()

    def test_local_search_priority_deduplication_and_ambiguity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            child = root / "library" / "with spaces" / "child.md"
            child.parent.mkdir(parents=True)
            child.write_text(LEAF, encoding="utf-8")
            top = root / "top.md"
            rows = [("slave_dir", str(root / "library")), ("slave_dir", str(child.parent))]
            slave(top, "child.md", rows)
            parser = CSRParser(str(top), nested=True)
            self.assertEqual(Path(parser.parse().sub_modules[0].source_path), child)
            self.assertEqual(len(parser.parse().base_info.slave_sources), 2)
            duplicate = root / "library" / "child.md"
            duplicate.write_text(LEAF, encoding="utf-8")
            with self.assertRaisesRegex(CSRValidationError, "ambiguous slave filename") as caught:
                parser.parse()
            self.assertIn(str(child), str(caught.exception))
            self.assertIn(str(duplicate), str(caught.exception))
            (root / "child.md").write_text(LEAF, encoding="utf-8")
            self.assertEqual(Path(parser.parse().sub_modules[0].source_path), root / "child.md")
            slave(top, "missing.md", rows)
            with self.assertRaisesRegex(FileNotFoundError, "slave file not found"):
                parser.parse()

    def test_filename_only_and_special_no_longer_contains_git(self):
        for filename in ("../child.md", "/tmp/a.md", "C:/a.xlsx", "doc\\a.md", "bad.txt"):
            with self.assertRaises(CSRValidationError):
                SlaveSources.validate_filename(filename)
        for name in ("a.md", "child.xlsx"):
            SlaveSources.validate_filename(name)
        with self.assertRaisesRegex(CSRValidationError, "unsupported special"):
            CSRParser("top.md")._validate_special("sub", "slave", parse_special(
                "slv_filename=child.md, git_url=https://example/repo.git", "slave"))

    def test_git_row_attributes_and_validation(self):
        rows = [("slave_git", " ref = v1 , path = doc/csr , url = https://example/repo.git"),
                ("slave_git", "url=git@example:team/second.git")]
        sources = parse_base_sources(rows, "fixture")
        self.assertEqual(sources, [{"git_url": "https://example/repo.git", "git_ref": "v1", "path": "doc/csr"},
                                   {"git_url": "git@example:team/second.git"}])
        self.assertEqual(parse_base_sources([(r[0], r[1]) for r in source_rows(sources)], "roundtrip"), sources)
        for value in ("path=docs", "url=", "url=https://example/repo.git, unknown=x",
                      "url=https://example/repo.git, ref=main, ref=v1", "url=https://example/repo.git, path=../escape",
                      "url=https://example/repo.git, path=/absolute", "url=ext::bad"):
            with self.subTest(value=value), self.assertRaises(CSRValidationError):
                parse_base_sources([("slave_git", value)], "fixture")
        with self.assertRaises(CSRValidationError):
            parse_base_sources([("slave_dir", "relative")], "fixture")
        self.assertEqual(parse_base_sources([("slave_dir", ""), ("slave_git", "-")], "fixture"), [])

    def test_removed_cli_options(self):
        parser = build_argument_parser()
        self.assertNotIn("--slave-", parser.format_help())
        for flag in ("--slave-dir", "--slave-git", "--slave-config"):
            with self.subTest(flag=flag), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                parser.parse_args(["-i", "top.md", flag, "value"])
            self.assertEqual(caught.exception.code, 2)

    def test_single_and_same_directory_do_not_fetch(self):
        with tempfile.TemporaryDirectory() as temp:
            top = Path(temp) / "top.md"
            slave(top, "child.md", [("slave_git", "url=https://example/repo.git")])
            with patch.object(SlaveSources, "git", side_effect=AssertionError("unexpected Git")):
                self.assertFalse(CSRParser(str(top)).parse().sub_modules)
                (top.parent / "child.md").write_text(LEAF, encoding="utf-8")
                self.assertEqual(len(CSRParser(str(top), nested=True).parse().sub_modules), 1)

    def test_cli_generates_nested_outputs_from_base_info(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / "docs").mkdir()
            (root / "docs" / "child.md").write_text(LEAF, encoding="utf-8")
            slave(root / "top.md", "child.md", [("slave_dir", str(root / "docs"))])
            self.assertEqual(main(["-i", str(root / "top.md"), "--nested", "-o", str(root / "out")]), 0)
            self.assertTrue(list((root / "out" / "rtl").glob("*.sv")))

    def test_repeated_rows_survive_markdown_and_excel_roundtrip(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            rows = [("slave_dir", str(root / "first")), ("slave_dir", str(root / "second")),
                    ("slave_git", "url=https://example/one.git, path=docs, ref=v1"),
                    ("slave_git", "url=https://example/two.git, ref=main")]
            top = root / "top.md"
            top.write_text(with_base(LEAF, rows), encoding="utf-8")
            model = CSRParser(str(top)).parse()
            self.assertEqual(len(model.base_info.slave_sources), 4)
            generated = DocGenerator(model, str(root / "out")).generate_all()
            for path in generated:
                if path.suffix in {".md", ".xlsx"}:
                    self.assertEqual(CSRParser(str(path)).parse().base_info.slave_sources, model.base_info.slave_sources)
            with (root / "out" / "top_gen.xlsx").open("rb") as stream:
                workbook = openpyxl.load_workbook(stream)
                try:
                    self.assertEqual([row[0].value for row in workbook["base_info"]].count("slave_git"), 2)
                finally:
                    workbook.close()

    def test_sources_inherit_without_leaking_into_siblings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            for name in ("modules", "global_docs", "private_docs"):
                (root / name).mkdir()
            slave(root / "modules" / "first.md", "leaf.md", [("slave_dir", str(root / "private_docs"))])
            slave(root / "modules" / "second.md", "other.md")
            (root / "private_docs" / "leaf.md").write_text(LEAF, encoding="utf-8")
            (root / "private_docs" / "other.md").write_text(LEAF, encoding="utf-8")
            (root / "global_docs" / "other.md").write_text(LEAF, encoding="utf-8")
            top = root / "top.md"
            rows = [("slave_dir", str(root / "modules")), ("slave_dir", str(root / "global_docs"))]
            text = HEADER + "| 0 | one | | | | | | slave | slv_filename=first.md, bytesize=0x100 | |\n| 0x100 | two | | | | | | slave | slv_filename=second.md, bytesize=0x100 | |\n"
            top.write_text(with_base(text, rows), encoding="utf-8")
            model = CSRParser(str(top), nested=True).parse()
            node = model.sub_modules[1].module_obj.sub_modules[0]
            self.assertEqual(Path(node.source_path), root / "global_docs" / "other.md")
            self.assertFalse(model.sub_modules[1].module_obj.base_info.slave_sources)

    @unittest.skipUnless(shutil.which("git"), "Git unavailable")
    def test_git_search_refs_relative_child_ambiguity_and_cycles(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            repo = root / "remote"
            repo.mkdir()

            def git(*args):
                return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                                      text=True, check=True).stdout.strip()

            def commit(message):
                git("add", ".")
                git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", message)

            git("init", "-b", "main")
            slave(repo / "docs" / "child.md", "leaf.md")
            (repo / "docs" / "leaf.md").write_text(LEAF, encoding="utf-8")
            commit("fixture")
            revision = git("rev-parse", "HEAD")
            git("tag", "v1")
            top = root / "top.md"
            for ref in ("HEAD", "main", "v1", revision):
                slave(top, "child.md", [("slave_git", f"url={repo.as_uri()}, ref={ref}, path=docs")])
                model = CSRParser(str(top), nested=True, repo_cache=str(root / "cache")).parse()
                self.assertEqual(model.sub_modules[0].module_obj.sub_modules[0].module_obj.name, "leaf")
                self.assertTrue(Path(model.sub_modules[0].source_path).is_file())
            resolver = SlaveSources(root / "cache", model.base_info.slave_sources)
            resolver.resolve("child.md", top)
            with patch.object(SlaveSources, "git", side_effect=AssertionError("duplicate fetch")):
                resolver.resolve("leaf.md", top)
            slave(top, "child.md", [("slave_git", f"url={repo.as_uri()}, ref=missing")])
            with self.assertRaisesRegex(CSRValidationError, "Git slave download failed"):
                CSRParser(str(top), nested=True).parse()
            slave(top, "child.md", [("slave_git", f"url={repo.as_uri()}, ref=main")])
            slave(repo / "docs" / "child.md", "child.md")
            commit("cycle")
            with self.assertRaisesRegex(CSRValidationError, "Recursive slave reference"):
                CSRParser(str(top), nested=True).parse()
            (repo / "child.md").write_text(LEAF, encoding="utf-8")
            commit("duplicate")
            with self.assertRaisesRegex(CSRValidationError, "ambiguous slave filename"):
                CSRParser(str(top), nested=True).parse()


if __name__ == "__main__":
    unittest.main()
