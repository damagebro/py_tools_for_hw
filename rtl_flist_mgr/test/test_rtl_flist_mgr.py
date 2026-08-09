from __future__ import annotations

import contextlib
import io
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
        shutil.copytree(EXAMPLE_DIR, self.work, dirs_exist_ok=True)

    def generate(self, mode: str) -> tuple[list[str], str]:
        output = self.work / "out" / f"soc_{mode}.f"
        code, stdout, stderr = self.invoke(
            ["soc.toml", "--workspace", str(self.work), "--mode", mode, "-o", str(output), "--path-style", "absolute"]
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

    def test_list_core_excludes_imported_cores(self) -> None:
        self.create_soc_workspace()
        code, stdout, stderr = self.invoke(["--workspace", str(self.work), "--list-core"])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("dmg:soc:top", stdout)
        self.assertNotIn("dmg:cpu:subsys", stdout)


if __name__ == "__main__":
    unittest.main()
