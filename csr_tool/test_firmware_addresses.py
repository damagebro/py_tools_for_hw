import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.models import BaseInfoModel, ModuleModel, RegisterModel, SubModuleNode
from src.reg_gen_firmware import generate_firmware


class FirmwareAddressTests(unittest.TestCase):
    def make_tree(self):
        leaf = ModuleModel(
            name="leaf", source_path="leaf.md",
            base_info=BaseInfoModel(common=True),
            registers=[RegisterModel("config", "config", 4, "cfg", "RW")],
        )
        mid = ModuleModel(name="mid", source_path="mid.md")
        mid.sub_modules.append(SubModuleNode("timer", 0x200, 0x100, "leaf.md", leaf))
        top = ModuleModel(
            name="top", source_path="top.md",
            base_info=BaseInfoModel(
                system_prefix="npu", system_baseaddr=0xF0000000, system_bytesize=0x10000,
            ),
        )
        for name, offset in (("mid_a", 0x1000), ("mid_b", 0x2000)):
            top.sub_modules.append(SubModuleNode(name, offset, 0x800, "mid.md", mid))
        return top

    def test_repeated_parent_instances_and_common_offsets(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate_firmware(self.make_tree(), tmp, True)
            addr = (Path(tmp) / "top_all_reg_addr.h").read_text(encoding="utf-8")
            defines = {
                parts[1]: parts[2]
                for line in addr.splitlines()
                if line.startswith("#define ") and len(parts := line.split(None, 2)) == 3
            }
            for index, instance in ((1, "MID_A"), (2, "MID_B")):
                self.assertEqual(defines[f"NPU_MID_U{index}_BASE_ADDR"], f"NPU_TOP_{instance}_SLV_ADDR")
                self.assertEqual(
                    defines[f"NPU_MID_U{index}_TIMER_SLV_ADDR"],
                    f"(NPU_MID_U{index}_BASE_ADDR + 0x00000200U)",
                )
                self.assertEqual(
                    defines[f"NPU_LEAF_U{index}_BASE_ADDR"],
                    f"NPU_MID_U{index}_TIMER_SLV_ADDR",
                )
            self.assertEqual([name for name in defines if name.endswith("_SYSTEM_ADDR")], ["NPU_TOP_SYSTEM_ADDR"])
            common = (Path(tmp) / "common/leaf_reg_addr.h").read_text(encoding="utf-8")
            self.assertNotIn("_SYSTEM_ADDR", common)
            self.assertNotIn("_SLV_ADDR", common)
            self.assertIn("LEAF_CONFIG_OFFSET", common)

    def test_default_system_address_and_wide_address(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = ModuleModel(name="cpu", source_path="cpu.md")
            for base, constant in ((0, "0x00000000U"), (0x100000000, "0x100000000ULL")):
                with self.subTest(base=base):
                    root.base_info.system_baseaddr = base
                    generate_firmware(root, tmp, True)
                    addr = (Path(tmp) / "cpu_all_reg_addr.h").read_text(encoding="utf-8")
                    self.assertIn(f"#ifndef CPU_CPU_SYSTEM_ADDR\n#define CPU_CPU_SYSTEM_ADDR {constant}\n#endif", addr)

    def test_address_macros_compile_with_root_overrides(self):
        compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            self.skipTest("C compiler not available")
        with tempfile.TemporaryDirectory() as tmp:
            generate_firmware(self.make_tree(), tmp, True)
            for override in (None, 0x10000000, 0xFE000000):
                with self.subTest(override=override):
                    base = 0xF0000000 if override is None else override
                    source = "" if override is None else f"#define NPU_TOP_SYSTEM_ADDR 0x{base:08X}U\n"
                    source += '#include "top_all_reg_addr.h"\n'
                    expected = {
                        "NPU_TOP_BASE_ADDR": base,
                        "NPU_TOP_END_ADDR": base + 0xFFFF,
                        "NPU_MID_U1_BASE_ADDR": base + 0x1000,
                        "NPU_MID_U2_END_ADDR": base + 0x27FF,
                        "NPU_LEAF_U1_BASE_ADDR": base + 0x1200,
                        "NPU_LEAF_U2_CONFIG_ADDR": base + 0x2204,
                    }
                    for macro, value in expected.items():
                        source += f'_Static_assert({macro} == 0x{value:X}U, "{macro}");\n'
                    source += f'_Static_assert(NPU_TOP_BASE_ADDR * 2ULL == 0x{base * 2:X}ULL, "precedence");\n'
                    result = subprocess.run(
                        [compiler, "-std=c11", "-Werror", "-fsyntax-only", "-x", "c", "-", "-I", tmp],
                        input=source, text=True, capture_output=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
