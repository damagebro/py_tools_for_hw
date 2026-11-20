from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from .models import ModuleModel, RegisterModel
from .reg_common import CSRValidationError, hex_width, write_text


@dataclass
class InstanceNode:
    module: ModuleModel
    path: tuple[str, ...]
    size: int
    parent_index: int | None
    instance_name: str
    unique_name: str


def generate_firmware(
    module: ModuleModel,
    out_dir: str,
    is_nested: bool = False,
) -> list[Path]:
    if not is_nested:
        return []
    common_headers = _common_headers(module)
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    prefix = (module.base_info.system_prefix or module.name).lower()
    addr_path = output / f"{module.name}_all_reg_addr.h"
    type_path = output / f"{module.name}_all_reg_type.h"
    legacy_dir = output / "c_legacy"
    field_path = legacy_dir / f"{module.name}_field_macros.h"
    stale_block_path = legacy_dir / f"{module.name}_block_macros.h"
    common_paths = []
    for filename, content in common_headers.items():
        common_path = output / "common" / filename
        write_text(common_path, content)
        common_paths.append(common_path)
    write_text(addr_path, _address_header(module, prefix, addr_path.name))
    write_text(type_path, _type_header(module, addr_path.name, type_path.name))
    write_text(field_path, _legacy_field_header(module, field_path.name))
    if stale_block_path.exists():
        stale_block_path.unlink()
    # Remove only the previous generated layout for the current module/blocks.
    stale_paths = [output / f"{module.name}_common_manifest.json"]
    stale_paths.extend(output / "common" / f"{b.name}_regs.h"
                       for b, _, _ in module.walk() if b.base_info.common)
    for stale in stale_paths:
        if stale.is_file():
            stale.unlink()
    return [addr_path, type_path, field_path, *common_paths]


def _common_includes(module: ModuleModel, kind: str, relative: str = "") -> list[str]:
    names = sorted({b.name for b, _, _ in module.walk() if b.base_info.common})
    directory = "c_legacy/" if kind == "field_macros" else ""
    return [f'#include "{relative}common/{directory}{name}_{kind}.h"' for name in names]


def _common_headers(module: ModuleModel) -> dict[str, str]:
    headers: dict[str, str] = {}
    definitions: dict[str, dict[str, str]] = {}
    source_paths: dict[str, str] = {}
    for block, _, _ in module.walk():
        if not block.base_info.common:
            continue
        # Only this block is shared; children and instance addresses stay outside.
        local = deepcopy(block)
        local.sub_modules = []
        local.base_info.common = False
        name = block.name
        addr_name = f"{name}_reg_addr.h"
        type_name = f"{name}_reg_type.h"
        field_name = f"{name}_field_macros.h"
        content = {
            addr_name: _address_header(local, "", addr_name, addresses=False),
            type_name: _type_header(local, addr_name, type_name),
            f"c_legacy/{field_name}": _legacy_field_header(local, field_name),
        }
        key = name.upper()
        if key in definitions and definitions[key] != content:
            raise CSRValidationError(
                f"Conflicting common block {name}: {source_paths[key]} vs {block.source_path}"
            )
        definitions[key] = content
        source_paths[key] = block.source_path
        headers.update(content)
    return headers


def _address_header(module: ModuleModel, prefix: str, filename: str, *, addresses: bool = True) -> str:
    guard = _guard(filename)
    nodes = list(module.walk())
    lines = [
        f"#ifndef {guard}",
        f"#define {guard}",
        "",
        "// Generated register offsets" + (" and absolute addresses." if addresses else " and defaults."),
        *_common_includes(module, "reg_addr"),
        "",
    ]
    seen_sources: set[str] = set()
    for block, _, _ in nodes:
        if block.base_info.common:
            continue
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

    if addresses:
        lines.append("// Absolute address map")
    instances = _instance_nodes(module) if addresses else []
    tags = [f"{prefix}_{node.unique_name}".upper() for node in instances]
    for node, block_tag in zip(instances, tags):
        block = node.module
        lines.append(f"// {'/'.join(node.path)}")
        if node.parent_index is None:
            system_addr = f"{block_tag}_SYSTEM_ADDR"
            lines.extend([
                f"#ifndef {system_addr}",
                *_define_lines([(system_addr, _c_hex(module.base_info.system_baseaddr, 32))]),
                "#endif",
            ])
            base_addr = f"({system_addr} + {_c_hex(0, 32)})"
        else:
            parent_tag = tags[node.parent_index]
            base_addr = f"{parent_tag}_{node.instance_name.upper()}_SLV_ADDR"
        defines = [
            (f"{block_tag}_BASE_ADDR", base_addr),
            (f"{block_tag}_SIZE", _c_hex(node.size, 32)),
            (f"{block_tag}_END_ADDR", f"({block_tag}_BASE_ADDR + {block_tag}_SIZE - 1U)"),
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
        slave_offsets = {reg.name: reg.offset for reg in block.registers if reg.reg_type == "slave"}
        slave_offsets.update((child.instance_name, child.offset) for child in block.sub_modules)
        for instance_name, offset in slave_offsets.items():
            defines.append((
                f"{block_tag}_{instance_name.upper()}_SLV_ADDR",
                f"({block_tag}_BASE_ADDR + {_c_hex(offset, 32)})",
            ))
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
        f'#include "{addr_filename}"' if addr_filename else "",
        *_common_includes(module, "reg_type"),
        "",
        "// Generated register type declarations. No storage is allocated.",
        "",
    ]
    seen_sources: set[str] = set()
    for block, _, _ in module.walk():
        if block.base_info.common:
            continue
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
        *_common_includes(module, "field_macros", "../"),
        "",
    ]
    seen_sources: set[str] = set()
    for block, _, _ in module.walk():
        if block.base_info.common:
            continue
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
    nodes: list[InstanceNode] = []

    def visit(
        item: ModuleModel,
        path: tuple[str, ...],
        allocated_size: int,
        parent_index: int | None,
        instance_name: str,
    ) -> None:
        current_path = path + (item.name,)
        index = len(nodes)
        nodes.append(InstanceNode(
            item, current_path, allocated_size, parent_index, instance_name, item.name,
        ))
        for child in item.sub_modules:
            visit(
                child.module_obj,
                current_path,
                child.bytesize,
                index,
                child.instance_name,
            )

    root_size = module.base_info.system_bytesize or module.local_size
    visit(module, (), root_size, None, "")
    name_counts = Counter(node.module.name for node in nodes)
    name_indexes: defaultdict[str, int] = defaultdict(int)
    for node in nodes:
        name = node.module.name
        name_indexes[name] += 1
        if name_counts[name] > 1:
            node.unique_name = f"{name}_u{name_indexes[name]}"
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
