from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SCRIPT_DIR))

from gen_rtl_dummy import (
    MODE_BBOX,
    MODE_PORT_SWAP,
    MODE_STUB,
    format_module_dummy,
    main,
    parse_modules,
)


class GenRtlDummyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rtl_path = Path(__file__).resolve().parent / "sample_rtl.sv"

    def generate(self, mode: str) -> str:
        modules = parse_modules(self.rtl_path.read_text(encoding="utf-8"))
        self.assertEqual(len(modules), 1)
        return format_module_dummy(modules[0], mode)

    def test_bbox_ties_outputs(self) -> None:
        output = self.generate(MODE_BBOX)
        self.assertIn("assign o_ready = '0;", output)
        self.assertIn("assign o_data  = '0;", output)
        self.assertIn("output wire o_ready", output)
        self.assertIn("output wire [DW-1:0] o_data", output)

    def test_stub_has_no_tie_assignment(self) -> None:
        output = self.generate(MODE_STUB)
        self.assertNotIn("assign", output)
        self.assertIn("output logic o_ready", output)

    def test_port_swap_swaps_direction_and_prefix(self) -> None:
        output = self.generate(MODE_PORT_SWAP)
        self.assertIn("output logic o_valid", output)
        self.assertIn("output logic [DW-1:0] o_data", output)
        self.assertIn("input logic i_ready", output)
        self.assertIn("input reg [DW-1:0] i_data", output)
        self.assertIn("inout wire io_pad", output)

    def test_main_accepts_relative_rtl_path(self) -> None:
        modules = parse_modules(self.rtl_path.read_text(encoding="utf-8"))
        with patch("gen_rtl_dummy.generate_dummy", return_value=modules):
            self.assertEqual(main(["test/sample_rtl.sv", "-o", "dummy.sv"]), 0)


if __name__ == "__main__":
    unittest.main()
