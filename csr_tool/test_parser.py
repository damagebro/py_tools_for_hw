from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from src.autogen_reg import run
from src.reg_common import CSRValidationError
from src.reg_parser import CSRParser


ROOT = Path(__file__).resolve().parent


class ParserTests(unittest.TestCase):
    def test_nested_address_map_and_name_deduplication(self) -> None:
        module = CSRParser(str(ROOT / "input" / "top_reg.md"), nested=True).parse()
        self.assertEqual(module.name, "top")
        self.assertEqual(
            [reg.name for reg in module.registers[-4:]],
            ["test1", "test2", "test3", "test4"],
        )
        addresses = [
            ("/".join(path), base) for _, base, path in module.walk()
        ]
        self.assertIn(("top/mid_a/leaf_a1", 0xF0001100), addresses)
        self.assertIn(("top/mid_b/leaf_a2", 0xF0002100), addresses)

    def test_generated_markdown_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            generated = run(
                str(ROOT / "input" / "leaf_a1_reg.md"),
                temp,
                nested=False,
            )
            markdown = Path(temp) / "doc" / "leaf_a1_gen.md"
            original = CSRParser(str(ROOT / "input" / "leaf_a1_reg.md")).parse()
            reparsed = CSRParser(str(markdown)).parse()
            self.assertEqual(
                [
                    (reg.name, reg.offset, reg.reg_type, reg.default_word())
                    for reg in original.registers
                ],
                [
                    (reg.name, reg.offset, reg.reg_type, reg.default_word())
                    for reg in reparsed.registers
                ],
            )
            self.assertIn(Path(temp) / "rtl" / "leaf_a1.sv", generated)

    def test_overlap_is_rejected(self) -> None:
        text = """# reg_define

| offset | reg_name | field | msb | lsb | SW_access | default_value | reg_type | special | description |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0x0 | first | value | 31 | 0 | RW | 0 | cfg | repeat 2 | |
| 0x4 | second | value | 31 | 0 | RW | 0 | cfg | - | |
"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.md"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(CSRValidationError, "Address overlap"):
                CSRParser(str(path)).parse()

    def test_reserved_field_name_is_rejected(self) -> None:
        text = """# reg_define

| offset | reg_name | field | msb | lsb | SW_access | default_value | reg_type | special | description |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0x0 | first | while | 0 | 0 | RW | 0 | cfg | - | |
"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.md"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(CSRValidationError, "reserved keyword"):
                CSRParser(str(path)).parse()

    def test_json_round_trip(self) -> None:
        original = CSRParser(str(ROOT / "input" / "leaf_a2_reg.md")).parse()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "leaf_a2.json"
            path.write_text(
                json.dumps(original.to_dict(), ensure_ascii=False),
                encoding="utf-8",
            )
            reparsed = CSRParser(str(path)).parse()
            self.assertEqual(
                [
                    (reg.name, reg.offset, reg.default_word())
                    for reg in original.registers
                ],
                [
                    (reg.name, reg.offset, reg.default_word())
                    for reg in reparsed.registers
                ],
            )

    def test_shadow_and_irq_generation(self) -> None:
        text = """# base_info

| item | type_input |
| --- | --- |
| reg_bitwidth | 32 |

# reg_define

| offset | reg_name | field | msb | lsb | SW_access | default_value | reg_type | special | description |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0x0 | cfg_queue | value | 7 | 0 | RW | 1,2 | cfg | repeat 2, shadow 4 | |
| 0x8 | irq_state | done | 0 | 0 | W1C | 0 | irq | - | |
"""
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "shadow_reg.md"
            source.write_text(text, encoding="utf-8")
            run(str(source), temp, nested=False)
            rtl = (Path(temp) / "rtl" / "shadow.sv").read_text(encoding="utf-8")
            self.assertIn("localparam integer SHADOW_DEPTH = 4;", rtl)
            self.assertIn("r_cfg_queue_value[r_shadow_wr_idx]", rtl)
            self.assertIn("assign o_irqclr_irq_state_done", rtl)
            self.assertNotIn("always_ff", rtl)

    def test_generated_rtl_port_columns_are_aligned(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run(
                str(ROOT / "input" / "top_reg.md"),
                temp,
                nested=True,
            )
            rtl = (Path(temp) / "rtl" / "top.sv").read_text(encoding="utf-8")
            port_block = rtl.split("(", 2)[2].split(");", 1)[0]
            port_lines = [
                line for line in port_block.splitlines()
                if line.strip().startswith(("input ", "output "))
            ]
            delimiter_columns = {
                line.index("//,") if "//," in line else line.index(",")
                for line in port_lines
            }
            self.assertEqual(len(delimiter_columns), 1)

            signal_columns = set()
            for line in port_lines:
                declaration = line.split("//,", 1)[0].rsplit(",", 1)[0]
                signal = declaration.split()[-1]
                signal_columns.add(line.index(signal))
            self.assertEqual(len(signal_columns), 1)


if __name__ == "__main__":
    unittest.main()
