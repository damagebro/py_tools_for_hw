from __future__ import annotations

import os
from pathlib import Path
import tempfile

from model import MEMORY_TYPES, InputFormatError, MemoryShape, validate_identifier
from rtl_template import RTL_TEMPLATES


START_MARKER = "// Start of user logic."
END_MARKER = "// End of user logic."

INSTANCE_PORTS = {
    "spram": (
        ("clk", "clk", "i"),
        ("i_cfg_mem_ctrl", "i_cfg_mem_ctrl", "i"),
        ("i_wr_en", "u_ram_i_wr_en", "i"),
        ("i_wr_addr", "u_ram_i_wr_addr", "i"),
        ("i_wr_data", "u_ram_i_wr_data", "i"),
        ("i_rd_en", "u_ram_i_rd_en", "i"),
        ("i_rd_addr", "u_ram_i_rd_addr", "i"),
        ("o_rd_data", "u_ram_o_rd_data", "o"),
    ),
    "tpram1ck": (
        ("clk", "clk", "i"),
        ("i_cfg_mem_ctrl", "i_cfg_mem_ctrl", "i"),
        ("i_wr_en", "u_ram_i_wr_en", "i"),
        ("i_wr_addr", "u_ram_i_wr_addr", "i"),
        ("i_wr_data", "u_ram_i_wr_data", "i"),
        ("i_rd_en", "u_ram_i_rd_en", "i"),
        ("i_rd_addr", "u_ram_i_rd_addr", "i"),
        ("o_rd_data", "u_ram_o_rd_data", "o"),
    ),
    "tpram2ck": (
        ("i_cfg_mem_ctrl", "i_cfg_mem_ctrl", "i"),
        ("wr_clk", "wr_clk", "i"),
        ("i_wr_en", "u_ram_i_wr_en", "i"),
        ("i_wr_addr", "u_ram_i_wr_addr", "i"),
        ("i_wr_data", "u_ram_i_wr_data", "i"),
        ("rd_clk", "rd_clk", "i"),
        ("i_rd_en", "u_ram_i_rd_en", "i"),
        ("i_rd_addr", "u_ram_i_rd_addr", "i"),
        ("o_rd_data", "u_ram_o_rd_data", "o"),
    ),
    "sprom": (
        ("clk", "clk", "i"),
        ("i_cfg_mem_ctrl", "i_cfg_mem_ctrl", "i"),
        ("i_rd_en", "u_rom_i_rd_en", "i"),
        ("i_rd_addr", "u_rom_i_rd_addr", "i"),
        ("o_rd_data", "u_rom_o_rd_data", "o"),
    ),
}


def atomic_write_text(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return True


def replace_generated_region(
    content: str,
    generated: str,
    *,
    source: Path,
    start_marker: str = START_MARKER,
    end_marker: str = END_MARKER,
) -> str:
    lines = content.splitlines(keepends=True)
    start_lines = [index for index, line in enumerate(lines) if start_marker in line]
    end_lines = [index for index, line in enumerate(lines) if end_marker in line]
    if len(start_lines) != 1 or len(end_lines) != 1:
        raise InputFormatError(
            f"{source}: expected exactly one {start_marker!r} and one "
            f"{end_marker!r}, found {len(start_lines)} and {len(end_lines)}"
        )
    start_index = start_lines[0]
    end_index = end_lines[0]
    if start_index >= end_index:
        raise InputFormatError(
            f"{source}: generated-region markers are in the wrong order"
        )
    generated_block = generated.rstrip()
    if generated_block:
        generated_block += "\n"
    return "".join(lines[: start_index + 1]) + generated_block + "".join(
        lines[end_index:]
    )


def _render_template(
    template_name: str,
    old_module_name: str,
    new_module_name: str,
) -> str:
    try:
        content = RTL_TEMPLATES[template_name]
    except KeyError as exc:
        raise InputFormatError(
            f"RTL template {template_name!r} is missing from rtl_template.py"
        ) from exc
    if old_module_name not in content:
        raise InputFormatError(
            f"{template_name}: module name {old_module_name!r} was not found"
        )
    return content.replace(old_module_name, new_module_name)


def _write_shell_set(
    work_path: Path,
    prefix: str,
    mem_type: str,
    *,
    preserve_manual: bool,
    generated_instances: str | None = None,
) -> tuple[Path, Path | None]:
    old_shell_name = f"com_{mem_type}_shell"
    new_shell_name = f"{prefix}_{mem_type}_shell"
    output_path = work_path / f"{new_shell_name}.sv"
    content = _render_template(
        f"{old_shell_name}.sv",
        old_shell_name,
        new_shell_name,
    )
    if generated_instances is not None:
        content = replace_generated_region(
            content,
            generated_instances,
            source=Path("rtl/shell") / f"{old_shell_name}.sv",
        )
    atomic_write_text(output_path, content)

    if mem_type != "sprom":
        old_ecc_name = f"com_ecc_{mem_type}_shell"
        new_ecc_name = f"{prefix}_ecc_{mem_type}_shell"
        ecc_content = _render_template(
            f"{old_ecc_name}.sv",
            old_ecc_name,
            new_ecc_name,
        ).replace(old_shell_name, new_shell_name)
        ecc_path = work_path / f"{new_ecc_name}.sv"
        atomic_write_text(ecc_path, ecc_content)
        return output_path, ecc_path

    old_manual_name = "com_sprom_manual"
    new_manual_name = f"{prefix}_sprom_manual"
    manual_path = work_path / f"{new_manual_name}.sv"
    if not preserve_manual or not manual_path.exists():
        manual_content = _render_template(
            f"{old_manual_name}.sv",
            old_manual_name,
            new_manual_name,
        ).replace(old_shell_name, new_shell_name)
        atomic_write_text(manual_path, manual_content)
    return output_path, manual_path


def generate_initial_shells(
    work_path: Path,
    prefix: str,
) -> list[Path]:
    validate_identifier(prefix, "subsys_prefix")
    outputs = []
    for mem_type in MEMORY_TYPES:
        generated = _write_shell_set(
            work_path,
            prefix,
            mem_type,
            preserve_manual=True,
            generated_instances=None,
        )
        outputs.extend(path for path in generated if path is not None)
    return outputs


def render_instances(mem_type: str, shapes: list[MemoryShape]) -> str:
    if not shapes:
        return "\n".join(
            [
                "    if( 0 ) begin:gen_none",
                "        assign use_cell = 1'b1;",
                "    end",
            ]
        )
    blocks = []
    for index, shape in enumerate(shapes):
        conditions = [
            f"DEPTH=={shape.depth}",
            f"DATA_W=={shape.width}",
        ]
        if mem_type != "sprom":
            conditions.append(f"STRB_W=={shape.strb_w}")
        conditions.append(f"MEM_USER=={shape.mem_user}")
        keyword = "if" if index == 0 else "else if"
        wrapper_name = shape.wrapper_name
        lines = [
            f"    {keyword}( {' && '.join(conditions)} ) begin:gen_sram_phy",
            f"        {wrapper_name} u_{wrapper_name}",
            "        (",
        ]
        ports = INSTANCE_PORTS[mem_type]
        for port_index, (port_name, signal_name, direction) in enumerate(ports):
            comma = "," if port_index < len(ports) - 1 else " "
            lines.append(
                f"            .{port_name:<19} "
                f"( {signal_name:<20} ){comma} //{direction}"
            )
        lines.extend(
            [
                "        );",
                "        assign use_cell = 1'b1;",
                "    end:gen_sram_phy",
            ]
        )
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def generate_integrated_shells(
    work_path: Path,
    prefix: str,
    shapes_by_type: dict[str, list[MemoryShape]],
) -> list[Path]:
    validate_identifier(prefix, "subsys_prefix")
    outputs = []
    for mem_type in MEMORY_TYPES:
        shell_output, extra_output = _write_shell_set(
            work_path,
            prefix,
            mem_type,
            preserve_manual=True,
            generated_instances=render_instances(
                mem_type,
                shapes_by_type.get(mem_type, []),
            ),
        )
        outputs.append(shell_output)
        if extra_output is not None:
            outputs.append(extra_output)
    return outputs
