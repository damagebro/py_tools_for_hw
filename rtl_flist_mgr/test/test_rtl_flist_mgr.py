from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import unittest
import uuid
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "src"
EXAMPLE_DIR = Path(__file__).resolve().parent / "examples" / "soc_cpu_npu"
sys.path.insert(0, str(SCRIPT_DIR))

import rtl_flist_mgr as mgr


class RtlFlistMgrTest(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(__file__).resolve().parent / "_work" / uuid.uuid4().hex
        self.work.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        (self.work / "import" / "cpu").mkdir(parents=True)
        (self.work / "import" / "npu").mkdir(parents=True)

    def write(self, relative: str, content: str = "module x; endmodule\n") -> Path:
        path = self.work / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def invoke(self, args: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = mgr.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def create_soc_workspace(self) -> None:
        shutil.copytree(EXAMPLE_DIR, self.work, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".rtl_flist"))
        sram_f = self.work / "import" / "cpu" / "filelist" / "sram_sim_model.f"
        sram_path = (self.work / "import" / "cpu" / "lsu" / "model" / "sram_sim_model.sv").as_posix()
        sram_f.write_text(f"# Legacy SRAM simulation model filelist.\n{sram_path}\n", encoding="utf-8")

    def generate(self, mode: str) -> tuple[list[str], str]:
        output = self.work / "out" / f"soc_{mode}.f"
        code, stdout, stderr = self.invoke(
            [
                "soc.toml",
                "--workspace",
                str(self.work),
                "--mode",
                mode,
                "-o",
                str(output),
                "--path-style",
                "absolute",
            ]
        )
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("resolved", stdout)
        return output.read_text(encoding="utf-8").splitlines(), (self.work / ".rtl_flist" / "core_tree.txt").read_text(encoding="utf-8")

    def test_soc_fileset_modes(self) -> None:
        self.create_soc_workspace()
        self.assertFalse((self.work / ".git_repo").exists())

        sim_lines, sim_tree = self.generate("sim")
        self.assertEqual(sim_lines[0], (self.work / "rtl/soc_pkg.sv").as_posix())
        self.assertIn((self.work / "import/cpu/lsu/model/sram_sim_model.sv").as_posix(), sim_lines)
        self.assertIn((self.work / "import/cpu/lsu/model/dw_sim_model.sv").as_posix(), sim_lines)
        self.assertLess(
            sim_lines.index((self.work / "import/cpu/cpu_subsys.sv").as_posix()),
            sim_lines.index((self.work / "import/npu/npu_subsys.sv").as_posix()),
        )
        self.assertIn("dmg:cpu:alu_harden", sim_tree)

        synth_lines, synth_tree = self.generate("synth")
        self.assertNotIn((self.work / "import/cpu/alu/alu_harden_top.sv").as_posix(), synth_lines)
        self.assertNotIn((self.work / "import/cpu/lsu/lsu_harden_top.sv").as_posix(), synth_lines)
        self.assertNotIn((self.work / "import/cpu/lsu/model/sram_sim_model.sv").as_posix(), synth_lines)
        self.assertIn((self.work / "import/cpu/alu_harden_stub.sv").as_posix(), synth_lines)
        self.assertIn(
            "module alu_harden_top",
            (self.work / "import/cpu/alu_harden_stub.sv").read_text(encoding="utf-8"),
        )
        self.assertNotIn("dmg:cpu:alu_harden", synth_tree)
        self.assertNotIn("dmg:cpu:lsu_harden", synth_tree)

        lint_lines, _ = self.generate("lint")
        self.assertIn((self.work / "import/cpu/alu/alu_harden_top.sv").as_posix(), lint_lines)
        self.assertIn((self.work / "import/cpu/lsu/lsu_harden_top.sv").as_posix(), lint_lines)
        self.assertNotIn((self.work / "import/cpu/lsu/model/sram_sim_model.sv").as_posix(), lint_lines)
        self.assertNotIn((self.work / "import/cpu/lsu/model/dw_sim_model.sv").as_posix(), lint_lines)

    def test_supports_common_capi2_core_subset(self) -> None:
        self.write("rtl/top.sv")
        self.write("top.toml", """
[core]
id = "dmg:soc:top"
filesets = ["rtl"]

[fileset.rtl]
files = ["rtl/top.sv"]
depend = ["dmg:legacy:leaf"]
""")
        self.write("import/cpu/rtl/leaf.sv")
        self.write("import/cpu/leaf.core", """
CAPI=2:
name: dmg:legacy:leaf
filesets:
  rtl:
    files:
      - rtl/leaf.sv: {file_type: systemVerilogSource}
targets:
  default:
    filesets: [rtl]
""")
        output = self.work / "out.f"
        code, _, stderr = self.invoke(["top.toml", "--workspace", str(self.work), "-o", str(output)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("import/cpu/rtl/leaf.sv", output.read_text(encoding="utf-8"))

    def test_reports_duplicate_core_id(self) -> None:
        self.create_soc_workspace()
        self.write("import/cpu/filelist/duplicate.toml", """
[core]
id = "dmg:cpu:subsys"

[fileset.rtl]
files = ["cpu_subsys.sv"]
""")
        code, _, stderr = self.invoke(["soc.toml", "--workspace", str(self.work), "-o", str(self.work / "out.f")])
        self.assertEqual(code, 1)
        self.assertIn("ERROR [E_CORE_ID_CONFLICT]", stderr)

    def test_rejects_removed_harden_metadata(self) -> None:
        self.write("rtl/top.sv")
        self.write("top.toml", """
[core]
id = "dmg:soc:top"
top_module_name = "top"

[fileset.rtl]
files = ["rtl/top.sv"]
""")
        code, _, stderr = self.invoke(["top.toml", "--workspace", str(self.work), "-o", str(self.work / "out.f")])
        self.assertEqual(code, 1)
        self.assertIn("ERROR [E_MANIFEST]: unsupported [core] property: top_module_name", stderr)

    def test_rejects_removed_toml_compile_options(self) -> None:
        self.write("rtl/top.sv")
        self.write("top.toml", """
[core]
id = "dmg:test:top"

[fileset.rtl]
files = ["rtl/top.sv"]
include_dirs = ["rtl/include"]
defines = ["TOP_ASSERT"]
file_type = "systemVerilogSource"
""")

        code, _, stderr = self.invoke(["top.toml", "--workspace", str(self.work), "-o", str(self.work / "out.f")])

        self.assertEqual(code, 1)
        self.assertIn("ERROR [E_MANIFEST]: unsupported [fileset.rtl] property: defines", stderr)

    def test_rejects_removed_toml_when(self) -> None:
        self.write("rtl/top.sv")
        self.write("top.toml", """
[core]
id = "dmg:test:top"

[fileset.rtl]
when = "is_sim"
files = ["rtl/top.sv"]
""")

        code, _, stderr = self.invoke(["top.toml", "--workspace", str(self.work), "-o", str(self.work / "out.f")])

        self.assertEqual(code, 1)
        self.assertIn("ERROR [E_MANIFEST]: unsupported [fileset.rtl] property: when", stderr)

    def test_supports_fusesoc_four_part_core_id(self) -> None:
        self.write("rtl/top.sv")
        self.write("top.toml", """
[core]
id = "dmg:soc:top:1.0.0"

[fileset.rtl]
files = ["rtl/top.sv"]
""")
        output = self.work / "out.f"
        code, _, stderr = self.invoke(["top.toml", "--workspace", str(self.work), "-o", str(output)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn((self.work / "rtl/top.sv").as_posix(), output.read_text(encoding="utf-8"))

    def test_supports_emu_and_fpga_modes(self) -> None:
        common_file = self.write("rtl/common.sv")
        emu_file = self.write("rtl/emu.sv")
        fpga_file = self.write("rtl/fpga.sv")
        synth_file = self.write("rtl/synth.sv")
        self.write("top.toml", """
[core]
id = "dmg:test:top"

[fileset.rtl]
files = [
  "rtl/common.sv",
  "is_emu ? (rtl/emu.sv)",
  "is_fpga ? (rtl/fpga.sv)",
  "is_synth ? (rtl/synth.sv)",
]
""")

        for mode, selected_file in (("emu", emu_file), ("fpga", fpga_file)):
            output = self.work / "out" / f"{mode}.f"
            code, _, stderr = self.invoke(["top.toml", "--workspace", str(self.work), "--mode", mode, "-o", str(output)])

            self.assertEqual((code, stderr), (0, ""))
            lines = output.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines, [common_file.as_posix(), selected_file.as_posix()])
            self.assertNotIn(synth_file.as_posix(), lines)

    def test_places_first_files_and_filesets_before_dependencies(self) -> None:
        normal_file = self.write("rtl/normal.sv")
        first_file = self.write("rtl/first.sv")
        prelude_file = self.write("rtl/prelude.sv")
        leaf_file = self.write("import/cpu/leaf.sv")
        self.write("top.toml", """
[core]
id = "dmg:test:top"
filesets = ["rtl", "first: prelude"]

[fileset.rtl]
files = ["rtl/normal.sv", "first: rtl/first.sv"]

[fileset.prelude]
depend = ["dmg:test:leaf"]
files = ["rtl/prelude.sv"]
""")
        self.write("import/cpu/leaf.toml", """
[core]
id = "dmg:test:leaf"

[fileset.rtl]
files = ["leaf.sv"]
""")
        output = self.work / "out.f"

        code, _, stderr = self.invoke(["top.toml", "--workspace", str(self.work), "-o", str(output)])

        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(
            output.read_text(encoding="utf-8").splitlines(),
            [first_file.as_posix(), prelude_file.as_posix(), normal_file.as_posix(), leaf_file.as_posix()],
        )

    def test_rejects_first_marker_in_depend(self) -> None:
        self.write("top.toml", """
[core]
id = "dmg:test:top"

[fileset.rtl]
depend = ["first: dmg:test:leaf"]
""")

        code, _, stderr = self.invoke(["top.toml", "--workspace", str(self.work), "-o", str(self.work / "out.f")])

        self.assertEqual(code, 1)
        self.assertIn("ERROR [E_MANIFEST]: first: is not supported in fileset.rtl.depend", stderr)

    def test_warns_for_same_filename_in_different_paths(self) -> None:
        cpu_file = self.write("rtl/cpu/spram100x10.sv")
        npu_file = self.write("rtl/npu/spram100x10.sv")
        self.write("top.toml", """
[core]
id = "dmg:test:top"

[fileset.rtl]
files = ["rtl/cpu/spram100x10.sv", "rtl/npu/spram100x10.sv"]
""")
        output = self.work / "out.f"

        code, _, stderr = self.invoke(["top.toml", "--workspace", str(self.work), "-o", str(output)])

        self.assertEqual(code, 0)
        self.assertIn("WARNING [W_FILE_NAME_CONFLICT]: 'spram100x10.sv'", stderr)
        self.assertIn(cpu_file.as_posix(), stderr)
        self.assertIn(npu_file.as_posix(), stderr)
        self.assertEqual(output.read_text(encoding="utf-8").splitlines(), [cpu_file.as_posix(), npu_file.as_posix()])

    def test_preserves_legacy_v_library_file(self) -> None:
        library_file = self.write("rtl/legacy_cell.v", "module legacy_cell; endmodule\n")
        self.write("legacy.f", "-v rtl/legacy_cell.v\n")
        self.write("top.toml", """
[core]
id = "dmg:test:top"

[fileset.rtl]
legacy_f = "legacy.f"
""")
        output = self.work / "out.f"

        code, _, stderr = self.invoke(["top.toml", "--workspace", str(self.work), "-o", str(output)])

        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(output.read_text(encoding="utf-8"), f"-v {library_file.as_posix()}\n")

    def test_supports_legacy_environment_variable_path(self) -> None:
        model_file = self.write("external/model.sv", "module model; endmodule\n")
        self.write("legacy.f", "${MODEL_ROOT}/model.sv\n")
        self.write("top.toml", """
[core]
id = "dmg:test:top"

[fileset.rtl]
legacy_f = "legacy.f"
""")
        output = self.work / "out.f"

        code, _, stderr = self.invoke(
            [
                "top.toml",
                "--workspace",
                str(self.work),
                "--var",
                f"MODEL_ROOT={model_file.parent}",
                "-o",
                str(output),
            ]
        )

        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(output.read_text(encoding="utf-8"), f"{model_file.as_posix()}\n")

    def test_preserves_legacy_compile_options(self) -> None:
        include_dir = self.work / "rtl" / "include"
        include_dir.mkdir(parents=True)
        source_file = self.write("rtl/top.sv")
        self.write("legacy.f", "+incdir+rtl/include\n+define+TOP_ASSERT=1\nrtl/top.sv\n")
        self.write("top.toml", """
[core]
id = "dmg:test:top"

[fileset.rtl]
legacy_f = "legacy.f"
""")
        output = self.work / "out.f"

        code, _, stderr = self.invoke(["top.toml", "--workspace", str(self.work), "-o", str(output)])

        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(
            output.read_text(encoding="utf-8"),
            f"+incdir+{include_dir.as_posix()}\n+define+TOP_ASSERT=1\n{source_file.as_posix()}\n",
        )

    def test_list_core_excludes_imported_cores(self) -> None:
        self.create_soc_workspace()
        code, stdout, stderr = self.invoke(["--workspace", str(self.work), "--list-core"])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("dmg:soc:top", stdout)
        self.assertNotIn("dmg:cpu:subsys", stdout)

    def test_core_index_cache_and_rescan(self) -> None:
        self.create_soc_workspace()
        index = self.work / ".rtl_flist" / "core_index.toml"

        code, stdout, stderr = self.invoke(["--workspace", str(self.work), "--list-core"])

        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("(scan)", stdout)
        self.assertTrue(index.is_file())
        self.assertIn('"dmg:cpu:subsys"', index.read_text(encoding="utf-8"))

        self.write("rtl/cache_added.sv")
        self.write("cache_added.toml", """
[core]
id = "dmg:test:cache_added"

[fileset.rtl]
files = ["rtl/cache_added.sv"]
""")

        code, stdout, stderr = self.invoke(["--workspace", str(self.work), "--list-core"])

        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("(cache)", stdout)
        self.assertNotIn("dmg:test:cache_added", stdout)

        code, stdout, stderr = self.invoke(["--workspace", str(self.work), "--list-core", "--rescan"])

        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("(rescan)", stdout)
        self.assertIn("dmg:test:cache_added", stdout)

    def test_list_core_directory(self) -> None:
        self.create_soc_workspace()
        directory = self.work / "import" / "cpu" / "filelist"
        code, stdout, stderr = self.invoke(["--list-core", "--directory", str(directory)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn(f"root_dir: {directory.resolve()} (--directory)", stdout)
        self.assertIn("dmg:cpu:subsys", stdout)
        self.assertIn("dmg:cpu:alu_harden", stdout)
        self.assertIn("dmg:cpu:lsu_harden", stdout)
        self.assertNotIn("dmg:npu:subsys", stdout)

    def test_list_core_finds_workspace_root_from_subdirectory(self) -> None:
        self.create_soc_workspace()
        previous = Path.cwd()
        os.chdir(self.work / "rtl")
        self.addCleanup(os.chdir, previous)
        code, stdout, stderr = self.invoke(["--list-core"])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn(f"root_dir: {self.work} (import)", stdout)
        self.assertIn("dmg:soc:top", stdout)
        self.assertNotIn("dmg:cpu:subsys", stdout)

    def test_list_core_finds_workspace_root_from_state_directory(self) -> None:
        self.write(".rtl_flist/.keep")
        self.write("rtl/top.sv")
        self.write("top.toml", """
[core]
id = "dmg:test:top"

[fileset.rtl]
files = ["rtl/top.sv"]
""")
        nested_directory = self.work / "rtl"
        previous = Path.cwd()
        os.chdir(nested_directory)
        self.addCleanup(os.chdir, previous)

        code, stdout, stderr = self.invoke(["--list-core"])

        self.assertEqual((code, stderr), (0, ""))
        self.assertIn(f"root_dir: {self.work} (.rtl_flist)", stdout)
        self.assertIn("dmg:test:top", stdout)


if __name__ == "__main__":
    unittest.main()
