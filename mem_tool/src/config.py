from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from model import InputFormatError, parse_int, validate_identifier


MODES = ("init", "sim", "excel", "inst", "all")


@dataclass(frozen=True, slots=True)
class ToolConfig:
    mode: str
    subsys_prefix: str
    work_path: Path
    excel_filename: str | None
    default_wr_clk_mhz: int
    default_rd_clk_mhz: int
    top_module: str | None = None
    filelist: str | None = None
    sim_env: tuple[str, ...] = ()
    sim_no_run: bool = False

    @property
    def excel_path(self) -> Path | None:
        if not self.excel_filename:
            return None
        return self.work_path / self.excel_filename


@dataclass(frozen=True, slots=True)
class JsonTemplateConfig:
    mode: str
    config_json: Path | None


def build_config_template(mode: str) -> dict[str, Any]:
    template: dict[str, Any] = {
        "mode": mode,
        "subsys_prefix": "cpu",
        "work_path": "./build",
    }
    if mode == "excel":
        template.update(
            {
                "excel_name": "cpu_memory_require.xlsx",
                "clk_a": 1500,
                "clk_b": 1000,
            }
        )
    elif mode == "inst":
        template.update(
            {
                "excel_name": "cpu_memory_require.xlsx",
            }
        )
    elif mode == "all":
        template.update(
            {
                "excel_name": "cpu_memory_require.xlsx",
                "clk_a": 1500,
                "clk_b": 1000,
                "top_module": "top_module",
                "filelist": "$PROJ_RTL/rtl.f",
                "sim_env": {
                    "PROJ_RTL": "C:/proj",
                },
            }
        )
    elif mode == "sim":
        template.update(
            {
                "top_module": "top_module",
                "filelist": "$PROJ_RTL/rtl.f",
                "sim_env": {
                    "PROJ_RTL": "C:/proj",
                },
            }
        )
    return template


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate memory shells, reports and integration RTL."
    )
    parser.add_argument(
        "-p",
        "--subsys_prefix",
        dest="subsys_prefix",
        help="subsystem prefix, such as cpu, npu or pcie",
    )
    parser.add_argument("-m", "--mode", choices=MODES)
    parser.add_argument("-w", "--work_path", type=Path)
    parser.add_argument(
        "-c",
        "--config_json",
        type=Path,
        help="JSON config file; with --gen_config_json, this is the output file",
    )
    parser.add_argument(
        "--gen_config_json",
        nargs="?",
        const="all",
        default=None,
        choices=MODES,
        metavar="MODE",
        help="generate a JSON config template; default mode is all",
    )
    parser.add_argument(
        "-x",
        "--excel_name",
        help="memory requirement workbook filename",
    )
    parser.add_argument(
        "-cka",
        "--clk_a",
        type=int,
        help=(
            "clock A in MHz: all single-clock memory accesses and "
            "tpram2ck writes"
        ),
    )
    parser.add_argument(
        "-ckb",
        "--clk_b",
        type=int,
        help="clock B in MHz: tpram2ck reads only",
    )
    parser.add_argument(
        "-t",
        "--top_module",
        help="top module instantiated by sim/tb/top.sv in sim mode",
    )
    parser.add_argument(
        "-f",
        "--filelist",
        help="project RTL filelist used by sim mode",
    )
    parser.add_argument(
        "-e",
        "--sim_env",
        action="append",
        metavar="NAME=VALUE",
        help="environment variable exported when running sim; can be repeated",
    )
    parser.add_argument(
        "--sim_no_run",
        dest="sim_no_run",
        action="store_true",
        default=None,
        help="only generate build/sim sandbox without invoking make",
    )
    parser.add_argument(
        "--sim_run",
        dest="sim_no_run",
        action="store_false",
        help="invoke make even if config_json sets sim_no_run=true",
    )
    return parser


def _load_json_config(path: Path) -> dict[str, Any]:
    try:
        with path.expanduser().open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise InputFormatError(f"cannot read config_json: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InputFormatError(f"invalid JSON config: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise InputFormatError("config_json root must be a JSON object")
    return dict(data)


def _normalize_sim_env(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        return tuple(f"{name}={env_value}" for name, env_value in value.items())
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value)
    raise InputFormatError("sim_env must be a JSON object or list")


def _merge_cli_value(data: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        data[key] = value


def parse_config(argv: Sequence[str] | None = None) -> ToolConfig | JsonTemplateConfig:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    if args.gen_config_json:
        return JsonTemplateConfig(
            mode=args.gen_config_json,
            config_json=args.config_json.expanduser().resolve()
            if args.config_json
            else None,
        )

    data: dict[str, Any] = {}
    if args.config_json:
        try:
            data.update(_load_json_config(args.config_json))
        except InputFormatError as exc:
            parser.error(str(exc))

    _merge_cli_value(data, "subsys_prefix", args.subsys_prefix)
    _merge_cli_value(data, "mode", args.mode)
    _merge_cli_value(data, "work_path", args.work_path)
    _merge_cli_value(data, "excel_name", args.excel_name)
    _merge_cli_value(data, "clk_a", args.clk_a)
    _merge_cli_value(data, "clk_b", args.clk_b)
    _merge_cli_value(data, "top_module", args.top_module)
    _merge_cli_value(data, "filelist", args.filelist)
    _merge_cli_value(data, "sim_env", args.sim_env)
    _merge_cli_value(data, "sim_no_run", args.sim_no_run)

    mode = str(data.get("mode") or "init").strip()
    if mode not in MODES:
        parser.error(f"mode must be one of {MODES}")
    subsys_prefix = str(data.get("subsys_prefix") or "").strip()
    if not subsys_prefix:
        parser.error("subsys_prefix is required")
    try:
        validate_identifier(subsys_prefix, "subsys_prefix")
    except InputFormatError as exc:
        parser.error(str(exc))

    work_path = Path(data.get("work_path") or "./").expanduser().resolve()
    excel_filename = (
        str(data.get("excel_name")).strip()
        if data.get("excel_name") is not None
        else None
    )
    if excel_filename:
        if Path(excel_filename).name != excel_filename:
            parser.error("excel_name must be a filename, not a directory path")
    if mode in ("excel", "all") and not excel_filename:
        parser.error(f"{mode} mode requires --excel_name")
    top_module = str(data.get("top_module")).strip() if data.get("top_module") else None
    if top_module:
        try:
            validate_identifier(top_module, "top_module")
        except InputFormatError as exc:
            parser.error(str(exc))
    try:
        sim_env = _normalize_sim_env(data.get("sim_env"))
    except InputFormatError as exc:
        parser.error(str(exc))
    for item in sim_env:
        if "=" not in item or not item.split("=", 1)[0]:
            parser.error("sim_env must use NAME=VALUE format")
        name = item.split("=", 1)[0]
        try:
            validate_identifier(name, "sim_env name")
        except InputFormatError as exc:
            parser.error(str(exc))
    filelist = str(data.get("filelist")).strip() if data.get("filelist") else None
    if mode in ("sim", "all"):
        if top_module is None:
            parser.error(f"{mode} mode requires --top_module")
        if filelist is None:
            parser.error(f"{mode} mode requires --filelist")
    sim_no_run = data.get("sim_no_run", False)
    if not isinstance(sim_no_run, bool):
        parser.error("sim_no_run must be a boolean")

    try:
        wr_clock = parse_int(data.get("clk_a", 1500), "clk_a", 1)
        rd_clock = parse_int(
            data.get("clk_b") if data.get("clk_b") is not None else wr_clock,
            "clk_b",
            1,
        )
    except InputFormatError as exc:
        parser.error(str(exc))

    return ToolConfig(
        mode=mode,
        subsys_prefix=subsys_prefix,
        work_path=work_path,
        excel_filename=excel_filename,
        default_wr_clk_mhz=wr_clock,
        default_rd_clk_mhz=rd_clock,
        top_module=top_module,
        filelist=filelist,
        sim_env=sim_env,
        sim_no_run=sim_no_run,
    )
