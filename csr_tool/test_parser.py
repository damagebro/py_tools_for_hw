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

    def test_vhdl_reserved_field_name_is_rejected(self) -> None:
        text = """# reg_define

| offset | reg_name | field | msb | lsb | SW_access | default_value | reg_type | special | description |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0x0 | first | architecture | 0 | 0 | RW | 0 | cfg | - | |
"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.md"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(
                CSRValidationError,
                "'architecture' is a reserved keyword",
            ):
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

    def test_tree_html_uses_register_detail_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run(
                str(ROOT / "input" / "top_reg.md"),
                temp,
                nested=True,
            )
            page = (Path(temp) / "doc" / "top_tree.html").read_text(
                encoding="utf-8"
            )
            self.assertIn('class="register-table"', page)
            for heading in (
                "reg_name",
                "address",
                "reg_type",
                "special",
                "SW_access",
                "field",
                "bit_scope",
                "default_value",
                "description",
            ):
                self.assertIn(f">{heading}<", page)
            self.assertNotIn(">SW<", page)
            self.assertNotIn(">HW<", page)
            self.assertNotIn(">msb<", page)
            self.assertNotIn(">lsb<", page)
            self.assertIn(">[31:0]<", page)
            self.assertEqual(page.count('<col style="width:20ch">'), 3 * 25)
            self.assertEqual(page.count('<col style="width:60ch">'), 25)
            self.assertIn('<aside class="sidebar">', page)
            self.assertIn('class="page-shell sidebar-collapsed"', page)
            self.assertIn('data-testid="sidebar-toggle"', page)
            self.assertIn('<a class="nav-address" href="#address-map">', page)
            self.assertIn('<details class="nav-module-group"', page)
            self.assertIn(
                '<summary class="nav-module">1 top</summary>',
                page,
            )
            self.assertIn(
                '<summary class="nav-module">1.1 mid_a</summary>',
                page,
            )
            self.assertIn(
                '<summary class="nav-module">1.1.1 leaf_a1</summary>',
                page,
            )
            self.assertIn(
                '<summary class="nav-module">1.1.2 leaf_a2_u1</summary>',
                page,
            )
            self.assertIn(
                '<summary class="nav-module">1.2.1 leaf_a2_u2</summary>',
                page,
            )
            self.assertNotIn("1.1 top/mid_a", page)
            self.assertNotIn("nav-overview", page)
            self.assertNotIn(">Overview<", page)
            self.assertIn('href="#module-1-reg-1"', page)
            self.assertIn('id="module-1-reg-1"', page)
            self.assertIn("top_ctrl (0xF0000000)", page)
            self.assertIn(
                '<h3 class="register-title" id="module-1-reg-1">'
                "top_ctrl (0xF0000000)</h3>",
                page,
            )
            self.assertIn(
                '<th class="meta-label">reg_name</th>'
                '<td class="meta-value">top_ctrl</td>',
                page,
            )
            self.assertNotIn(
                '<td class="meta-value">top_ctrl (0xF0000000)</td>',
                page,
            )
            self.assertIn("0xF0000000 ~ 0xF000FFFF", page)
            self.assertIn("0xF0001000 ~ 0xF00017FF", page)
            self.assertIn(">bytesize<", page)
            self.assertIn(">0x800<", page)
            self.assertIn(">block<", page)
            self.assertIn(">1.1 mid_a<", page)
            self.assertNotIn(">path<", page)
            self.assertNotIn("top/mid_a", page)
            self.assertNotIn(">source<", page)
            self.assertNotIn(">base_address<", page)
            self.assertIn(">address<", page)
            self.assertIn(">0xF0001000<", page)
            self.assertNotIn(">offset<", page)
            self.assertIn("<summary>1.1 mid_a</summary>", page)
            self.assertNotIn("<code>0xF0001000</code>", page)
            self.assertIn('class="address-table"', page)
            self.assertEqual(page.count('<col style="width:30ch">'), 3)

    def test_tree_markdown_uses_absolute_addresses(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run(
                str(ROOT / "input" / "top_reg.md"),
                temp,
                nested=True,
            )
            tree = (Path(temp) / "doc" / "top_tree.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("| block", tree)
            self.assertIn("| 1 top", tree)
            self.assertIn("| 1.1 mid_a", tree)
            self.assertIn("| 1.1.2 leaf_a2_u1", tree)
            self.assertIn("| 1.2.1 leaf_a2_u2", tree)
            self.assertNotIn("top/mid_a", tree)
            self.assertNotIn("Base address:", tree)
            self.assertNotIn("Source:", tree)
            self.assertIn("| address", tree)
            self.assertIn("| 0xF0000000 | top_ctrl", tree)
            self.assertIn("| 0xF0001000 | mid_cfg", tree)
            self.assertIn("| 0xF0001100 | ver", tree)

    def test_tree_excel_uses_absolute_addresses(self) -> None:
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl is unavailable")
        with tempfile.TemporaryDirectory() as temp:
            run(
                str(ROOT / "input" / "top_reg.md"),
                temp,
                nested=True,
            )
            workbook = openpyxl.load_workbook(
                Path(temp) / "doc" / "top_tree.xlsx",
                read_only=True,
                data_only=True,
            )
            try:
                address_rows = list(workbook["address_map"].values)
                self.assertEqual(
                    address_rows[0],
                    ("block", "address_range", "bytesize", "link"),
                )
                self.assertEqual(address_rows[2][0], "1.1 mid_a")
                self.assertNotIn("top/mid_a", address_rows[2])
                self.assertEqual(address_rows[4][0], "1.1.2 leaf_a2_u1")
                self.assertEqual(address_rows[6][0], "1.2.1 leaf_a2_u2")
                self.assertIn("1_1_2_leaf_a2_u1", workbook.sheetnames)
                self.assertIn("1_2_1_leaf_a2_u2", workbook.sheetnames)

                mid_rows = list(workbook["1_1_mid_a"].values)
                self.assertEqual(mid_rows[0][0], "address")
                self.assertEqual(mid_rows[1][0], "0xF0001000")
                self.assertEqual(mid_rows[1][1], "mid_cfg")
            finally:
                workbook.close()


if __name__ == "__main__":
    unittest.main()
