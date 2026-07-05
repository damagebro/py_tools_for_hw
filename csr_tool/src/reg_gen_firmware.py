from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .models import ModuleModel, RegisterModel
from .reg_common import hex_width, write_text


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
    write_text(addr_path, _address_header(module, prefix, addr_path.name))
    write_text(type_path, _type_header(module, addr_path.name, type_path.name))
    return [addr_path, type_path]


def _address_header(module: ModuleModel, prefix: str, filename: str) -> str:
    guard = _guard(filename)
    nodes = list(module.walk())
    block_counts = Counter(item.name for item, _, _ in nodes)
    block_indexes: defaultdict[str, int] = defaultdict(int)
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
        for reg in block.registers:
            if reg.reg_type in {"slave", "mem"}:
                continue
            suffixes = range(reg.repeat) if reg.repeat > 1 else [None]
            for index in suffixes:
                reg_tag = f"{reg.name}_{index}" if index is not None else reg.name
                offset = reg.offset + (index or 0) * block.word_bytes
                width = hex_width(max(32, block.base_info.reg_bitwidth))
                lines.append(
                    f"#define {block.name.upper()}_{reg_tag.upper()}_OFFSET "
                    f"0x{offset:0{width}X}U"
                )
                lines.append(
                    f"#define {block.name.upper()}_{reg_tag.upper()}_DEFAULT "
                    f"0x{reg.default_word(index or 0):0{width}X}U"
                )
        lines.append("")

    lines.append("// Absolute address map")
    for block, base, path in nodes:
        block_indexes[block.name] += 1
        unique = block.name
        if block_counts[block.name] > 1:
            unique = f"{block.name}_u{block_indexes[block.name]}"
        block_tag = f"{prefix}_{unique}".upper()
        lines.append(f"// {'/'.join(path)}")
        lines.append(f"#define {block_tag}_BASE_ADDR 0x{base:08X}U")
        for reg in block.registers:
            if reg.reg_type in {"slave", "mem"}:
                continue
            suffixes = range(reg.repeat) if reg.repeat > 1 else [None]
            for index in suffixes:
                reg_tag = f"{reg.name}_{index}" if index is not None else reg.name
                lines.append(
                    f"#define {block_tag}_{reg_tag.upper()}_ADDR "
                    f"({block_tag}_BASE_ADDR + "
                    f"{block.name.upper()}_{reg_tag.upper()}_OFFSET)"
                )
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


def _guard(filename: str) -> str:
    return filename.replace(".", "_").replace("-", "_").upper()
