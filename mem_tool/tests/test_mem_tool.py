from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


MEM_TOOL_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = MEM_TOOL_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from config import JsonTemplateConfig, ToolConfig, build_config_template, parse_config
from excel_io import parse_memory_excel, write_memory_excel
from get_rtl_template import OUTPUT_PATH, SHELL_PATH, render_rtl_template
from main import run
from model import MEMORY_TYPES, InputFormatError, MemoryShape
from report import parse_report_directory, parse_report_file
from rtl_template import RTL_TEMPLATES
from rtl_gen import (
    generate_initial_shells,
    generate_integrated_shells,
    replace_generated_region,
)
from sim_run import run_memory_sim


class ReportTests(unittest.TestCase):
    def test_fixture_parses_and_aggregates(self) -> None:
        fixture = MEM_TOOL_ROOT / "tests" / "fixtures" / "spram.lst"
        shapes = parse_report_file(fixture, "cpu")
        self.assertEqual(len(shapes), 9)
        target = next(
            shape for shape in shapes if shape.raw_shape == "spram1024x128"
        )
        self.assertEqual(target.instance_num, 3)
        self.assertEqual(target.hierarchy, "top.aa,top.aa.bb,top.aa.bb.cc")

    def test_invalid_report_has_line_number(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spram.lst"
            path.write_text("not a memory report\n", encoding="utf-8")
            with self.assertRaisesRegex(InputFormatError, r"spram\.lst:1"):
                parse_report_file(path, "cpu")

    def test_directory_accepts_mixed_report_types(self) -> None:
        fixture = MEM_TOOL_ROOT / "tests" / "fixtures" / "spram.lst"
        with tempfile.TemporaryDirectory() as directory:
            work_path = Path(directory)
            (work_path / "spram.lst").write_text(
                fixture.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            result = parse_report_directory(work_path, "cpu")
            self.assertEqual(set(result), set(MEMORY_TYPES))
            self.assertEqual(len(result["tpram2ck"]), 1)
            self.assertEqual(len(result["sprom"]), 1)
            target = next(
                shape
                for shape in result["spram"]
                if shape.raw_shape == "spram1024x128"
            )
            self.assertEqual(target.instance_num, 3)


class ExcelTests(unittest.TestCase):
    def test_round_trip_includes_last_row(self) -> None:
        shapes = {mem_type: [] for mem_type in MEMORY_TYPES}
        shapes["spram"].append(
            MemoryShape(
                mem_type="spram",
                prefix="cpu",
                depth=64,
                width=32,
                strb_w=4,
                hierarchy="top.u_spram",
            )
        )
        shapes["tpram2ck"].append(
            MemoryShape(
                mem_type="tpram2ck",
                prefix="cpu",
                depth=128,
                width=64,
                strb_w=8,
                mem_user=2,
                suffix="usr2",
                hierarchy="top.u_tpram",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.xlsx"
            write_memory_excel(
                shapes,
                path,
                default_wr_clk_mhz=1500,
                default_rd_clk_mhz=1000,
            )
            parsed = parse_memory_excel(path)
        self.assertEqual(len(parsed["spram"]), 1)
        self.assertEqual(len(parsed["tpram2ck"]), 1)
        self.assertEqual(parsed["tpram2ck"][0].depth, 128)
        self.assertEqual(parsed["tpram2ck"][0].rd_clk_mhz, 1000)
        self.assertEqual(parsed["spram"][0].hierarchy, "top.u_spram")
        self.assertEqual(parsed["tpram2ck"][0].hierarchy, "top.u_tpram")

    def test_duplicate_conditions_are_rejected(self) -> None:
        shapes = {mem_type: [] for mem_type in MEMORY_TYPES}
        shapes["spram"] = [
            MemoryShape("spram", "cpu", 64, 32, 4),
            MemoryShape("spram", "cpu", 64, 32, 4, suffix="other"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.xlsx"
            write_memory_excel(
                shapes,
                path,
                default_wr_clk_mhz=1500,
                default_rd_clk_mhz=1000,
            )
            with self.assertRaisesRegex(
                InputFormatError, "duplicate memory condition"
            ):
                parse_memory_excel(path)


class RtlGenerationTests(unittest.TestCase):
    def test_embedded_templates_match_shell_sources(self) -> None:
        source_names = {
            path.name for path in SHELL_PATH.glob("*.sv")
        }
        self.assertEqual(set(RTL_TEMPLATES), source_names)
        for name, content in RTL_TEMPLATES.items():
            self.assertEqual(
                content,
                (SHELL_PATH / name).read_text(encoding="utf-8"),
            )
        self.assertEqual(
            OUTPUT_PATH.read_text(encoding="utf-8"),
            render_rtl_template(),
        )

    def test_missing_phy_check_defaults_to_model(self) -> None:
        expected = {
            "com_spram_shell.sv": "com_spram_not_found",
            "com_tpram1ck_shell.sv": "com_tpram1ck_not_found",
            "com_tpram2ck_shell.sv": "com_tpram2ck_not_found",
        }
        for name, missing_module in expected.items():
            content = (SHELL_PATH / name).read_text(encoding="utf-8")
            strict_branch, default_branch = content.split(
                "`ifdef COM_RAM_NFOUND_CHK", 1
            )[1].split("`else", 1)
            default_branch = default_branch.split("`endif", 1)[0]
            self.assertIn(missing_module, strict_branch)
            self.assertIn("com_tpram_reg", default_branch)

        sprom = (SHELL_PATH / "com_sprom_shell.sv").read_text(
            encoding="utf-8"
        )
        strict_branch = sprom.split("`ifdef COM_RAM_NFOUND_CHK", 1)[1].split(
            "`endif", 1
        )[0]
        self.assertIn("com_sprom_not_found", strict_branch)

    def test_missing_marker_fails_without_modifying_text(self) -> None:
        with self.assertRaisesRegex(InputFormatError, "expected exactly one"):
            replace_generated_region(
                "module test;\nendmodule\n",
                "generated",
                source=Path("test.sv"),
            )

    def test_manual_rom_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work_path = Path(directory)
            generate_initial_shells(work_path, "cpu")
            manual_path = work_path / "cpu_sprom_manual.sv"
            custom = manual_path.read_text(encoding="utf-8") + "// custom ROM\n"
            manual_path.write_text(custom, encoding="utf-8")
            generate_initial_shells(work_path, "cpu")
            self.assertEqual(manual_path.read_text(encoding="utf-8"), custom)

    def test_integrated_generation_is_idempotent(self) -> None:
        shapes = {mem_type: [] for mem_type in MEMORY_TYPES}
        shapes["spram"].append(
            MemoryShape(
                mem_type="spram",
                prefix="cpu",
                depth=64,
                width=32,
                strb_w=4,
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            work_path = Path(directory)
            outputs = generate_integrated_shells(
                work_path,
                "cpu",
                shapes,
            )
            shell_path = work_path / "cpu_spram_shell.sv"
            first_content = shell_path.read_text(encoding="utf-8")
            first_times = {
                path: path.stat().st_mtime_ns
                for path in outputs
                if path.is_file()
            }
            outputs = generate_integrated_shells(
                work_path,
                "cpu",
                shapes,
            )
            second_times = {
                path: path.stat().st_mtime_ns
                for path in outputs
                if path.is_file()
            }
            self.assertIn("cpu_spram_64x32x4_wrapper", first_content)
            empty_shell = (work_path / "cpu_tpram1ck_shell.sv").read_text(
                encoding="utf-8"
            )
            self.assertIn("if( 0 ) begin:gen_none", empty_shell)
            self.assertEqual(first_times, second_times)


class ConfigTests(unittest.TestCase):
    def test_cli_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = parse_config(
                [
                    "-p",
                    "cpu",
                    "-m",
                    "excel",
                    "-w",
                    directory,
                    "-x",
                    "memory.xlsx",
                    "-cka",
                    "1400",
                    "-ckb",
                    "900",
                ]
            )
        self.assertEqual(config.mode, "excel")
        self.assertEqual(config.subsys_prefix, "cpu")
        self.assertEqual(config.default_wr_clk_mhz, 1400)
        self.assertEqual(config.default_rd_clk_mhz, 900)

    def test_sim_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            filelist = Path(directory) / "rtl.f"
            filelist.write_text("// project rtl\n", encoding="utf-8")
            config = parse_config(
                [
                    "-p",
                    "cpu",
                    "-m",
                    "sim",
                    "-w",
                    directory,
                    "-t",
                    "cpu_top",
                    "-f",
                    str(filelist),
                    "--sim_no_run",
                ]
            )
        self.assertEqual(config.mode, "sim")
        self.assertEqual(config.top_module, "cpu_top")
        self.assertEqual(config.filelist, str(filelist))
        self.assertTrue(config.sim_no_run)

    def test_json_sim_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work_path = Path(directory)
            filelist = work_path / "rtl.f"
            filelist.write_text("// project rtl\n", encoding="utf-8")
            config_json = work_path / "sim_config.json"
            config_json.write_text(
                json.dumps(
                    {
                        "mode": "sim",
                        "subsys_prefix": "cpu",
                        "work_path": str(work_path),
                        "top_module": "cpu_top",
                        "filelist": "$PROJ_RTL/rtl.f",
                        "sim_env": {
                            "PROJ_RTL": str(work_path).replace("\\", "/"),
                        },
                        "sim_no_run": True,
                    }
                ),
                encoding="utf-8",
            )
            config = parse_config(["-c", str(config_json), "--sim_run"])
        self.assertEqual(config.mode, "sim")
        self.assertEqual(config.sim_env, (f"PROJ_RTL={work_path.as_posix()}",))
        self.assertFalse(config.sim_no_run)

    def test_gen_config_json_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = parse_config(
                [
                    "--gen_config_json",
                    "-c",
                    str(Path(directory) / "sim_config.json"),
                ]
            )
        self.assertIsInstance(config, JsonTemplateConfig)
        self.assertEqual(config.mode, "all")

    def test_minimal_json_templates(self) -> None:
        self.assertEqual(
            build_config_template("init"),
            {
                "mode": "init",
                "subsys_prefix": "cpu",
                "work_path": "./build",
            },
        )
        self.assertEqual(
            build_config_template("excel"),
            {
                "mode": "excel",
                "subsys_prefix": "cpu",
                "work_path": "./build",
                "excel_name": "cpu_memory_require.xlsx",
                "clk_a": 1500,
                "clk_b": 1000,
            },
        )
        self.assertEqual(
            build_config_template("inst"),
            {
                "mode": "inst",
                "subsys_prefix": "cpu",
                "work_path": "./build",
                "excel_name": "cpu_memory_require.xlsx",
            },
        )
        self.assertIn("top_module", build_config_template("sim"))
        self.assertEqual(
            build_config_template("all"),
            {
                "mode": "all",
                "subsys_prefix": "cpu",
                "work_path": "./build",
                "excel_name": "cpu_memory_require.xlsx",
                "clk_a": 1500,
                "clk_b": 1000,
                "top_module": "top_module",
                "filelist": "$PROJ_RTL/rtl.f",
                "sim_env": {
                    "PROJ_RTL": "C:/proj",
                },
            },
        )

    def test_explicit_missing_excel_does_not_fall_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ToolConfig(
                mode="inst",
                subsys_prefix="cpu",
                work_path=Path(directory),
                excel_filename="missing.xlsx",
                default_wr_clk_mhz=1500,
                default_rd_clk_mhz=1000,
            )
            with self.assertRaisesRegex(InputFormatError, "does not exist"):
                run(config)


class SimRunTests(unittest.TestCase):
    def test_generate_sim_sandbox_without_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work_path = Path(directory)
            filelist = work_path / "project.f"
            filelist.write_text("// project rtl\n", encoding="utf-8")
            outputs = run_memory_sim(
                work_path,
                "cpu",
                "cpu_top",
                str(filelist),
                no_run=True,
            )
            top_sv = work_path / "sim" / "tb" / "top.sv"
            rtl_f = work_path / "sim" / "rtl.f"
            self.assertIn(top_sv, outputs)
            self.assertIn(rtl_f, outputs)
            self.assertIn(
                "cpu_top u_cpu_top();",
                top_sv.read_text(encoding="utf-8"),
            )
            self.assertIn(
                f"-f {filelist.resolve().as_posix()}",
                rtl_f.read_text(encoding="utf-8"),
            )
            for relative_path in (
                "define/impl_define.sv",
                "define/impl_define_sim.sv",
                "model/com_tpram_reg.sv",
            ):
                self.assertTrue(
                    (work_path / "sim" / "rtl" / relative_path).is_file()
                )


if __name__ == "__main__":
    unittest.main()
