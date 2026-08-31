from __future__ import annotations

import io
import sys
import unittest
import shutil
import uuid
from contextlib import redirect_stdout
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SCRIPT_DIR))

from gen_rtl_inst import main, parse_modules


class GenRtlInstTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rtl_path = Path(__file__).resolve().parent / "test.sv"

    def make_workdir(self) -> Path:
        path = Path(__file__).resolve().parent / "_work" / uuid.uuid4().hex
        path.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path

    def test_parser_extracts_parameters_and_ports(self) -> None:
        modules = parse_modules(self.rtl_path.read_text(encoding="utf-8"))
        self.assertEqual([module.name for module in modules], ["sample_sv", "sample_v95"])
        sample_sv = modules[0]
        self.assertEqual([parameter.name for parameter in sample_sv.parameters], ["DW", "PAYLOAD_T", "LANES", "EXTRA"])
        self.assertNotIn("HIDDEN", [parameter.name for parameter in sample_sv.parameters])
        self.assertIn("m_axi", [port.name for port in sample_sv.ports])

    def test_main_generates_instance_snippet(self) -> None:
        output = self.make_workdir() / "inst.sv"
        self.assertEqual(main([str(self.rtl_path), "-o", str(output)]), 0)
        content = output.read_text(encoding="utf-8")
        self.assertIn("sample_sv #(", content)
        self.assertIn(".EXTRA", content)
        self.assertNotIn(".HIDDEN", content)
        self.assertIn(".clk", content)
        self.assertIn("u_sample_sv_inst", content)

    def test_stdout_contains_only_instance_snippet(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([str(self.rtl_path), "--stdout"]), 0)
        content = output.getvalue()
        self.assertTrue(content.startswith(f"// Source: {self.rtl_path}"))
        self.assertIn("u_sample_sv_inst", content)
        self.assertNotIn("generated inst.sv", content)


if __name__ == "__main__":
    unittest.main()
