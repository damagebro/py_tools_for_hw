from __future__ import annotations

import os
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import sys

from model import InputFormatError, MemToolError, validate_identifier
from rtl_gen import (
    atomic_write_text,
    generate_initial_shells,
    replace_generated_region,
)


MEM_TOOL_ROOT = Path(__file__).resolve().parents[1]
PY_SIM_TEMPLATE = MEM_TOOL_ROOT / "templates" / "py_sim" / "gen_tb.py"
RTL_TEMPLATE_DIR = MEM_TOOL_ROOT / "templates" / "rtl"

SHELL_START_MARKER = "// AUTO_MEM_SHELL_FILELIST_BEGIN"
SHELL_END_MARKER = "// AUTO_MEM_SHELL_FILELIST_END"
ENV_REF_RE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
DEFINE_SECTION = """//--------------------------------------
//define
//--------------------------------------

"""


def _generate_sim_template(
    sim_dir: Path,
    *,
    top_module: str,
    filelist: str,
    sim_env: dict[str, str],
) -> list[Path]:
    if not PY_SIM_TEMPLATE.is_file():
        raise InputFormatError(f"py sim template does not exist: {PY_SIM_TEMPLATE}")
    spec = importlib.util.spec_from_file_location("mem_tool_gen_tb", PY_SIM_TEMPLATE)
    if spec is None or spec.loader is None:
        raise InputFormatError(f"cannot load py sim template: {PY_SIM_TEMPLATE}")
    gen_tb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen_tb)
    return gen_tb.generate_tb(
        sim_dir,
        top_module=top_module,
        filelist=filelist,
        sim_env=sim_env,
    )


def _copy_rtl_template(sim_dir: Path) -> list[Path]:
    if not RTL_TEMPLATE_DIR.is_dir():
        raise InputFormatError(f"rtl template does not exist: {RTL_TEMPLATE_DIR}")
    rtl_dir = sim_dir / "rtl"
    outputs: list[Path] = []
    for source in RTL_TEMPLATE_DIR.rglob("*"):
        if "__pycache__" in source.parts or source.suffix in (".py", ".pyc"):
            continue
        target = rtl_dir / source.relative_to(RTL_TEMPLATE_DIR)
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        outputs.append(target)
    return outputs


def _reset_sim_dir(work_path: Path) -> Path:
    sim_dir = work_path / "sim"
    if sim_dir.exists():
        work_root = work_path.resolve()
        sim_root = sim_dir.resolve()
        if sim_root.parent != work_root or sim_root.name != "sim":
            raise InputFormatError(f"refuse to remove unexpected sim dir: {sim_root}")
        shutil.rmtree(sim_root)
    sim_dir.mkdir(parents=True, exist_ok=True)
    return sim_dir


def _prepare_sim_rtl(sim_dir: Path, prefix: str) -> list[Path]:
    return generate_initial_shells(sim_dir / "rtl" / "shell", prefix)


def _patch_shell_filelist(sim_dir: Path, shell_paths: list[Path]) -> Path:
    rtl_f = sim_dir / "rtl.f"
    content = rtl_f.read_text(encoding="utf-8")
    content = content.replace(
        DEFINE_SECTION,
        DEFINE_SECTION + "${SIM_DIR}/rtl/define/impl_define_sim.sv\n\n",
        1,
    )
    generated = "".join(
        (
            "${SIM_DIR}/rtl/dw/com_ecc_secded.sv\n",
            "${SIM_DIR}/rtl/model/com_tpram_reg.sv\n",
            "\n",
        )
    )
    generated += "".join(
        f"${{SIM_DIR}}/rtl/shell/{path.name}\n" for path in shell_paths
    )
    patched = replace_generated_region(
        content,
        generated,
        source=rtl_f,
        start_marker=SHELL_START_MARKER,
        end_marker=SHELL_END_MARKER,
    )
    atomic_write_text(rtl_f, patched)
    return rtl_f


def _parse_env(sim_env: tuple[str, ...]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in sim_env:
        name, value = item.split("=", 1)
        parsed[name] = value
    return parsed


def _expand_env_path(value: str, sim_env: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        assert name is not None
        if name in sim_env:
            return sim_env[name]
        if name in os.environ:
            return os.environ[name]
        raise InputFormatError(
            f"filelist uses environment variable {name!r}, "
            "but it was not provided by --sim_env"
        )

    return ENV_REF_RE.sub(replace, value)


def _warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)


def _normalize_filelist(
    filelist: str,
    sim_env: dict[str, str],
    *,
    allow_missing: bool,
) -> str:
    has_env = ENV_REF_RE.search(filelist) is not None
    try:
        expanded = _expand_env_path(filelist, sim_env) if has_env else filelist
    except InputFormatError as exc:
        if not allow_missing:
            raise
        _warn(str(exc))
        return filelist
    expanded_path = Path(expanded).expanduser()
    if not expanded_path.is_absolute():
        message = (
            "filelist is not an absolute path or an environment-variable "
            f"based path: {filelist}"
        )
        if not allow_missing:
            raise InputFormatError(message)
        _warn(message)
        return filelist
    if not expanded_path.is_file():
        message = f"filelist does not exist: {expanded_path}"
        if not allow_missing:
            raise InputFormatError(message)
        _warn(message)
        return filelist
    if has_env:
        return filelist
    return expanded_path.resolve().as_posix()


def _run_make(sim_dir: Path, sim_env: dict[str, str]) -> None:
    env = os.environ.copy()
    env.update(sim_env)
    for target in ("com", "run"):
        command = f"source ./ENV.sh && make {target}"
        try:
            result = subprocess.run(
                ["bash", "-lc", command],
                cwd=sim_dir,
                check=False,
                env=env,
            )
        except FileNotFoundError as exc:
            raise MemToolError(
                "bash was not found; rerun with --sim_no_run to only generate "
                "the sim sandbox"
            ) from exc
        if result.returncode != 0:
            raise MemToolError(f"sim make target failed: {target}")


def run_memory_sim(
    work_path: Path,
    prefix: str,
    top_module: str,
    filelist: str,
    *,
    sim_env: tuple[str, ...] = (),
    no_run: bool = False,
) -> list[Path]:
    env = _parse_env(sim_env)
    validate_identifier(top_module, "top_module")
    filelist = _normalize_filelist(filelist, env, allow_missing=no_run)
    sim_dir = _reset_sim_dir(work_path)
    outputs = _generate_sim_template(
        sim_dir,
        top_module=top_module,
        filelist=filelist,
        sim_env=env,
    )
    outputs.extend(_copy_rtl_template(sim_dir))
    rtl_outputs = _prepare_sim_rtl(sim_dir, prefix)
    outputs.extend(rtl_outputs)
    shell_outputs = [
        path for path in rtl_outputs if path.parent == sim_dir / "rtl" / "shell"
    ]
    outputs.append(_patch_shell_filelist(sim_dir, shell_outputs))
    if not no_run:
        _run_make(sim_dir, env)
    return sorted(set(outputs))
