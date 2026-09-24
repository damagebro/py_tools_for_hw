import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from src.models import ModuleModel, SubModuleNode
from src.reg_common import CSRValidationError
from src.reg_gen_firmware import generate_firmware
from src.reg_parser import CSRParser

ROOT = Path(__file__).resolve().parent


class CommonFirmwareTests(unittest.TestCase):
    def test_common_boolean(self):
        parser = CSRParser(str(ROOT / "input/leaf_a2_reg.md"))
        self.assertTrue(parser.parse().base_info.common)
        self.assertFalse(parser._parse_base_info([], Path("sample.md")).common)
        for value in (True, "true", "TRUE"):
            self.assertTrue(parser._parse_base_info([("common", value)], Path("sample.xlsx")).common)
        self.assertFalse(parser._parse_base_info([("common", False)], Path("sample.xlsx")).common)
        with self.assertRaisesRegex(CSRValidationError, "common must"):
            parser._parse_base_info([("common", "yes")], Path("sample.md"))

    def test_reuse_and_conflict(self):
        leaf = CSRParser(str(ROOT / "input/leaf_a2_reg.md")).parse()
        roots = []
        for name in ("cpu", "npu"):
            root = ModuleModel(name=name, source_path=f"{name}.md")
            for index in range(2):
                copy = deepcopy(leaf)
                copy.source_path = f"{name}/copy{index}/leaf_a2.md"
                root.sub_modules.append(SubModuleNode(f"timer{index}", 0x100 * index, 0x100, copy.source_path, copy))
            roots.append(root)
        with tempfile.TemporaryDirectory() as tmp:
            outputs = []
            for root in roots:
                out = Path(tmp) / root.name
                generated = generate_firmware(root, str(out), True)
                contents = {}
                for name in ("leaf_a2_reg_addr.h", "leaf_a2_reg_type.h", "c_legacy/leaf_a2_field_macros.h"):
                    shared = out / "common" / name
                    self.assertEqual(generated.count(shared), 1)
                    contents[name] = shared.read_text(encoding="utf-8")
                    self.assertNotIn("_BASE_ADDR", contents[name])
                    self.assertNotIn("HASH", contents[name])
                    self.assertNotIn("#error", contents[name])
                self.assertIn("leaf_a2_block_reg_set_default", contents["leaf_a2_reg_type.h"])
                self.assertIn('#include "leaf_a2_reg_addr.h"', contents["leaf_a2_reg_type.h"])
                self.assertNotIn("typedef", contents["leaf_a2_reg_addr.h"])
                self.assertNotIn("_MASK", contents["leaf_a2_reg_addr.h"])
                outputs.append(contents)
                self.assertFalse((out / f"{root.name}_common_manifest.json").exists())
                addr = (out / f"{root.name}_all_reg_addr.h").read_text()
                self.assertIn(f"{root.name.upper()}_LEAF_A2_U2_BASE_ADDR", addr)
            self.assertEqual(outputs[0], outputs[1])
            roots[0].sub_modules[1].module_obj.registers[0].offset += 4
            with self.assertRaisesRegex(CSRValidationError, "Conflicting common block"):
                generate_firmware(roots[0], str(Path(tmp) / "conflict"), True)
            self.assertFalse((Path(tmp) / "conflict").exists())

    def test_flag_does_not_propagate(self):
        root = CSRParser(str(ROOT / "input/top_reg.md"), nested=True).parse()
        root.base_info.common = True
        with tempfile.TemporaryDirectory() as tmp:
            generate_firmware(root, tmp, True)
            names = {p.name for p in (Path(tmp) / "common").glob("*.h")}
            self.assertEqual(names, {"top_reg_addr.h", "top_reg_type.h", "leaf_a2_reg_addr.h", "leaf_a2_reg_type.h"})

    def test_old_output_cleanup(self):
        leaf = CSRParser(str(ROOT / "input/leaf_a2_reg.md")).parse()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "common").mkdir()
            old = out / "common/leaf_a2_regs.h"
            manifest = out / "leaf_a2_common_manifest.json"
            unrelated = out / "common/user_header.h"
            for file in (old, manifest, unrelated):
                file.write_text("old", encoding="utf-8")
            generate_firmware(leaf, tmp, True)
            self.assertFalse(old.exists())
            self.assertFalse(manifest.exists())
            self.assertTrue(unrelated.exists())


if __name__ == "__main__":
    unittest.main()
