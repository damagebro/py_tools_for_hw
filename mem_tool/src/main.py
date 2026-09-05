from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Sequence

from config import (
    JsonTemplateConfig,
    ToolConfig,
    build_config_template,
    parse_config,
)
from excel_io import parse_memory_excel, write_memory_excel
from model import MemToolError
from report import parse_report_directory
from rtl_gen import generate_initial_shells, generate_integrated_shells
from sim_run import run_memory_sim


def _load_shapes(config: ToolConfig):
    if config.excel_path is not None:
        return parse_memory_excel(config.excel_path)
    return parse_report_directory(config.work_path, config.subsys_prefix)


def run_all(config: ToolConfig) -> list[Path]:
    assert config.excel_path is not None
    assert config.top_module is not None
    assert config.filelist is not None

    outputs: list[Path] = []
    outputs.extend(
        generate_initial_shells(
            config.work_path,
            config.subsys_prefix,
        )
    )
    outputs.extend(
        run_memory_sim(
            config.work_path,
            config.subsys_prefix,
            config.top_module,
            config.filelist,
            sim_env=config.sim_env,
            no_run=config.sim_no_run,
        )
    )
    shapes = parse_report_directory(
        config.work_path,
        config.subsys_prefix,
    )
    write_memory_excel(
        shapes,
        config.excel_path,
        default_wr_clk_mhz=config.default_wr_clk_mhz,
        default_rd_clk_mhz=config.default_rd_clk_mhz,
    )
    outputs.append(config.excel_path)
    outputs.extend(
        generate_integrated_shells(
            config.work_path,
            config.subsys_prefix,
            shapes,
        )
    )
    return sorted(set(outputs))


def run(config: ToolConfig) -> list[Path]:
    if config.mode == "init":
        return generate_initial_shells(
            config.work_path,
            config.subsys_prefix,
        )
    if config.mode == "excel":
        shapes = parse_report_directory(
            config.work_path,
            config.subsys_prefix,
        )
        assert config.excel_path is not None
        write_memory_excel(
            shapes,
            config.excel_path,
            default_wr_clk_mhz=config.default_wr_clk_mhz,
            default_rd_clk_mhz=config.default_rd_clk_mhz,
        )
        return [config.excel_path]
    if config.mode == "sim":
        assert config.top_module is not None
        assert config.filelist is not None
        return run_memory_sim(
            config.work_path,
            config.subsys_prefix,
            config.top_module,
            config.filelist,
            sim_env=config.sim_env,
            no_run=config.sim_no_run,
        )
    if config.mode == "inst":
        shapes = _load_shapes(config)
        return generate_integrated_shells(
            config.work_path,
            config.subsys_prefix,
            shapes,
        )
    if config.mode == "all":
        return run_all(config)
    raise MemToolError(f"unsupported mode: {config.mode}")


def write_config_template(config: JsonTemplateConfig) -> list[Path]:
    content = json.dumps(
        build_config_template(config.mode),
        ensure_ascii=False,
        indent=4,
    )
    if config.config_json is None:
        print(content)
        return []
    config.config_json.parent.mkdir(parents=True, exist_ok=True)
    config.config_json.write_text(content + "\n", encoding="utf-8")
    return [config.config_json]


def main(argv: Sequence[str] | None = None) -> int:
    try:
        config = parse_config(argv)
        if isinstance(config, JsonTemplateConfig):
            outputs = write_config_template(config)
            if config.config_json is None:
                return 0
            mode = "gen_config_json"
            work_path = config.config_json.parent if config.config_json else Path("./")
        else:
            outputs = run(config)
            mode = config.mode
            work_path = config.work_path
    except MemToolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        f"{mode} completed: {len(outputs)} output file(s) in "
        f"{work_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
