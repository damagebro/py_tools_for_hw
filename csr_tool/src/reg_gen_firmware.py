from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .models import ModuleModel, RegisterModel
from .reg_common import hex_width, write_text


InstanceNode = tuple[ModuleModel, int, tuple[str, ...], int, str]


def generate_firmware(
    module: ModuleModel,
    out_dir: str,
    is_nested: bool = False,
) -> list[Path]:
    if not is_nested:
        return []
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    prefix = (module.base_info.system_prefix or module.name).lower()
    addr_path = output / f"{module.name}_all_reg_addr.h"
    type_path = output / f"{module.name}_all_reg_type.h"
    legacy_dir = output / "c_legacy"
    field_path = legacy_dir / f"{module.name}_field_macros.h"
    stale_block_path = legacy_dir / f"{module.name}_block_macros.h"
    write_text(addr_path, _address_header(module, prefix, addr_path.name))
    write_text(type_path, _type_header(module, addr_path.name, type_path.name))
    write_text(field_path, _legacy_field_header(module, field_path.name))
    if stale_block_path.exists():
        stale_block_path.unlink()
    return [addr_path, type_path, field_path]


def _address_header(module: ModuleModel, prefix: str, filename: str) -> str:
    guard = _guard(filename)
    nodes = list(module.walk())
    lines = [
        f"#ifndef {guard}",
        f"#define {guard}",
        "",
        "// Generated register offsets and absolute addresses.",
        "",
    ]
    seen_sources: set[str] = set()
    for block, _, _ in nodes:
        source = str(Path(block.source_path).resolve()).lower()
        if source in seen_sources:
            continue
        seen_sources.add(source)
        lines.append(f"// {block.name} register offsets")
        defines: list[tuple[str, str]] = []
        for reg in block.registers:
            if reg.reg_type in {"slave", "mem"}:
                continue
            suffixes = range(reg.repeat) if reg.repeat > 1 else [None]
            for index in suffixes:
                reg_tag = f"{reg.name}_{index}" if index is not None else reg.name
                offset = reg.offset + (index or 0) * block.word_bytes
                width = hex_width(max(32, block.base_info.reg_bitwidth))
                defines.append(
                    (
                        f"{block.name.upper()}_{reg_tag.upper()}_OFFSET",
                        f"0x{offset:0{width}X}U",
                    )
                )
                defines.append(
                    (
                        f"{block.name.upper()}_{reg_tag.upper()}_DEFAULT",
                        f"0x{reg.default_word(index or 0):0{width}X}U",
                    )
                )
        lines.extend(_define_lines(defines))
        lines.append("")

    lines.append("// Absolute address map")
    for block, base, path, size, unique in _instance_nodes(module):
        block_tag = f"{prefix}_{unique}".upper()
        lines.append(f"// {'/'.join(path)}")
        end_addr = base + max(1, size) - 1
        defines = [
            (f"{block_tag}_BASE_ADDR", f"0x{base:08X}U"),
            (f"{block_tag}_SIZE", _c_hex(size, 32)),
            (f"{block_tag}_END_ADDR", _c_hex(end_addr, 32)),
        ]
        for reg in block.registers:
            if reg.reg_type in {"slave", "mem"}:
                continue
            suffixes = range(reg.repeat) if reg.repeat > 1 else [None]
            for index in suffixes:
                reg_tag = f"{reg.name}_{index}" if index is not None else reg.name
                defines.append(
                    (
                        f"{block_tag}_{reg_tag.upper()}_ADDR",
                        f"({block_tag}_BASE_ADDR + "
                        f"{block.name.upper()}_{reg_tag.upper()}_OFFSET)",
                    )
                )
                defines.append(
                    (
                        f"{block_tag}_{reg_tag.upper()}_DEFAULT",
                        f"{block.name.upper()}_{reg_tag.upper()}_DEFAULT",
                    )
                )
        lines.extend(_define_lines(defines))
        lines.append("")
    lines.extend([f"#endif // {guard}"])
    return "\n".join(lines)


def _type_header(module: ModuleModel, addr_filename: str, filename: str) -> str:
    guard = _guard(filename)
    lines = [
        f"#ifndef {guard}",
        f"#define {guard}",
        "",
        "#include <stdint.h>",
        f'#include "{addr_filename}"',
        "",
        "// Generated register type declarations. No storage is allocated.",
        "",
    ]
    seen_sources: set[str] = set()
    for block, _, _ in module.walk():
        source = str(Path(block.source_path).resolve()).lower()
        if source in seen_sources:
            continue
        seen_sources.add(source)
        scalar = "uint64_t" if block.base_info.reg_bitwidth > 32 else "uint32_t"
        lines.extend(_block_separator(block.name))
        for reg in block.registers:
            if reg.reg_type in {"slave", "mem"}:
                continue
            tag = f"{block.name}_{reg.name}"
            lines.extend(_register_union(reg, tag, scalar, block.base_info.reg_bitwidth))
        lines.append(f"typedef struct {block.name}_block_reg_s {{")
        for reg in block.registers:
            if reg.reg_type in {"slave", "mem"}:
                continue
            array = f"[{reg.repeat}]" if reg.repeat > 1 else ""
            lines.append(
                f"    {block.name}_{reg.name}_tu {reg.name}{array};"
            )
        lines.extend([
            f"}} {block.name}_block_reg_ts;",
            "",
        ])
        lines.extend(_block_default_function(block))
    lines.append(f"#endif // {guard}")
    return "\n".join(lines)


def _block_default_function(block: ModuleModel) -> list[str]:
    lines = [
        f"static inline void {block.name}_block_reg_set_default(",
        f"    {block.name}_block_reg_ts *regs",
        ") {",
        "    if (!regs) {",
        "        return;",
        "    }",
    ]
    for reg in block.registers:
        if reg.reg_type in {"slave", "mem"}:
            continue
        if reg.repeat > 1:
            for index in range(reg.repeat):
                reg_tag = f"{reg.name}_{index}"
                lines.append(
                    f"    regs->{reg.name}[{index}].word = "
                    f"{block.name.upper()}_{reg_tag.upper()}_DEFAULT;"
                )
        else:
            lines.append(
                f"    regs->{reg.name}.word = "
                f"{block.name.upper()}_{reg.name.upper()}_DEFAULT;"
            )
    lines.extend([
        "}",
        "",
    ])
    return lines


def _block_separator(block_name: str) -> list[str]:
    return [
        "// -----------------------------------------------------------------------------",
        f"// {block_name} block",
        "// -----------------------------------------------------------------------------",
        "",
    ]


def _legacy_field_header(module: ModuleModel, filename: str) -> str:
    guard = _guard(filename)
    lines = [
        f"#ifndef {guard}",
        f"#define {guard}",
        "",
        "// Legacy C-compatible field mask and shift macros.",
        "",
    ]
    seen_sources: set[str] = set()
    for block, _, _ in module.walk():
        source = str(Path(block.source_path).resolve()).lower()
        if source in seen_sources:
            continue
        seen_sources.add(source)
        lines.append(f"// {block.name} fields")
        defines: list[tuple[str, str]] = []
        for reg in block.registers:
            if reg.reg_type in {"slave", "mem"}:
                continue
            for field in reg.fields:
                tag = f"{block.name}_{reg.name}_{field.name}".upper()
                mask = ((1 << field.width) - 1) << field.lsb
                defines.extend([
                    (f"{tag}_LSB", f"{field.lsb}U"),
                    (f"{tag}_MSB", f"{field.msb}U"),
                    (f"{tag}_WIDTH", f"{field.width}U"),
                    (f"{tag}_MASK", _c_hex(mask, block.base_info.reg_bitwidth)),
                    (
                        f"{tag}_GET(value)",
                        f"(((value) & {tag}_MASK) >> {tag}_LSB)",
                    ),
                    (
                        f"{tag}_SET(value)",
                        f"(((value) << {tag}_LSB) & {tag}_MASK)",
                    ),
                ])
        lines.extend(_define_lines(defines))
        lines.append("")
    lines.append(f"#endif // {guard}")
    return "\n".join(lines)


def _register_union(
    reg: RegisterModel,
    tag: str,
    scalar: str,
    bitwidth: int,
) -> list[str]:
    lines = [
        f"// SW_access={reg.sw_access}, reg_type={reg.reg_type}",
        f"typedef union {tag}_u {{",
        "    struct {",
    ]
    cursor = 0
    for field in sorted(reg.fields, key=lambda item: item.lsb):
        if field.lsb > cursor:
            lines.append(
                f"        {scalar} rsv{field.lsb - 1}_{cursor} : "
                f"{field.lsb - cursor};"
            )
        lines.append(
            f"        {scalar} {field.name} : {field.width}; "
            f"// default=0x{field.default_for(0):X}"
        )
        cursor = field.msb + 1
    if cursor < bitwidth:
        lines.append(
            f"        {scalar} rsv{bitwidth - 1}_{cursor} : {bitwidth - cursor};"
        )
    lines.extend([
        "    } bits;",
        f"    {scalar} word;",
        f"}} {tag}_tu;",
        "",
    ])
    return lines


def _instance_nodes(module: ModuleModel) -> list[InstanceNode]:
    raw_nodes: list[tuple[ModuleModel, int, tuple[str, ...], int]] = []

    def visit(
        item: ModuleModel,
        absolute_base: int,
        path: tuple[str, ...],
        allocated_size: int,
    ) -> None:
        current_path = path + (item.name,)
        raw_nodes.append((item, absolute_base, current_path, allocated_size))
        for child in item.sub_modules:
            visit(
                child.module_obj,
                absolute_base + child.offset,
                current_path,
                child.bytesize,
            )

    root_size = module.base_info.system_bytesize or module.local_size
    visit(module, module.base_info.system_baseaddr, (), root_size)
    name_counts = Counter(item.name for item, _, _, _ in raw_nodes)
    name_indexes: defaultdict[str, int] = defaultdict(int)
    nodes: list[InstanceNode] = []
    for item, base, path, size in raw_nodes:
        name_indexes[item.name] += 1
        unique_name = item.name
        if name_counts[item.name] > 1:
            unique_name = f"{item.name}_u{name_indexes[item.name]}"
        nodes.append((item, base, path, size, unique_name))
    return nodes


def _c_hex(value: int, bitwidth: int) -> str:
    width = max(8, hex_width(max(32, bitwidth)))
    suffix = "ULL" if bitwidth > 32 or value > 0xFFFFFFFF else "U"
    return f"0x{value:0{width}X}{suffix}"


def _define_lines(defines: list[tuple[str, str]]) -> list[str]:
    if not defines:
        return []
    name_width = max(len(name) for name, _ in defines)
    return [f"#define {name:<{name_width}} {value}" for name, value in defines]


def _guard(filename: str) -> str:
    return filename.replace(".", "_").replace("-", "_").upper()
