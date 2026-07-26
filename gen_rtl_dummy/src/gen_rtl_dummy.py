#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


PARSER_DIR = Path(__file__).resolve().parents[2] / "gen_rtl_inst" / "src"
if not PARSER_DIR.is_dir():
    raise RuntimeError(f"gen_rtl_inst parser directory not found: {PARSER_DIR}")
sys.path.insert(0, str(PARSER_DIR))

from gen_rtl_inst import ModuleInfo, Port, normalize_space, parse_modules


MODE_BBOX = "bbox"
MODE_STUB = "stub"
MODE_PORT_SWAP = "port_swap"
MODE_SET = {MODE_BBOX, MODE_STUB, MODE_PORT_SWAP}
NET_TYPE_RE = re.compile(
    r"^(?:wire|tri|tri0|tri1|wand|wor|uwire|supply0|supply1)\b"
)


def invert_port_name(name: str) -> str:
    if name.startswith("i_"):
        return f"o_{name[2:]}"
    if name.startswith("o_"):
        return f"i_{name[2:]}"
    return name


def invert_direction(direction: str) -> str:
    if direction == "i":
        return "o"
    if direction == "o":
        return "i"
    return direction


def direction_text(direction: str) -> str:
    directions = {"i": "input", "o": "output", "io": "inout"}
    if direction not in directions:
        raise ValueError(f"unsupported port direction: {direction}")
    return directions[direction]


def bbox_output_type(type_text: str) -> str:
    text = normalize_space(type_text)
    if not text:
        return "wire"
    if NET_TYPE_RE.match(text):
        return text
    text = re.sub(r"\breg\b", "wire", text, count=1)
    text = re.sub(r"\blogic\b", "wire", text, count=1)
    if NET_TYPE_RE.match(text):
        return text
    return f"wire {text}"


def format_port_decl(port: Port, mode: str) -> str:
    if port.direction == "?":
        raise ValueError(f"direction not found for port: {port.name}")
    if port.direction == "if":
        type_text = normalize_space(port.type_text) or "interface"
        unpacked = f" {port.unpacked}" if port.unpacked else ""
        return f"{type_text} {port.name}{unpacked}"

    direction = port.direction
    name = port.name
    type_text = normalize_space(port.type_text)
    if mode == MODE_PORT_SWAP:
        direction = invert_direction(direction)
        if port.direction in {"i", "o"}:
            name = invert_port_name(name)
    if mode == MODE_BBOX and direction == "o":
        type_text = bbox_output_type(type_text)

    unpacked = f" {port.unpacked}" if port.unpacked else ""
    type_part = f" {type_text}" if type_text else ""
    return f"{direction_text(direction)}{type_part} {name}{unpacked}"


def format_parameter_decl(name: str, default: str) -> str:
    if default == "<must_be_specified>":
        return f"parameter {name}"
    return f"parameter {name} = {default}"


def format_module_header(module: ModuleInfo, mode: str) -> list[str]:
    lines: list[str] = []
    if module.parameters:
        lines.append(f"module {module.name} #(")
        param_width = max(len(parameter.name) for parameter in module.parameters)
        for index, parameter in enumerate(module.parameters):
            comma = "," if index < len(module.parameters) - 1 else ""
            declaration = format_parameter_decl(parameter.name, parameter.default)
            lines.append(f"    {declaration:<{param_width + 12}}{comma}")
        lines.append(")")
    else:
        lines.append(f"module {module.name}")

    lines.append("(")
    for index, port in enumerate(module.ports):
        comma = "," if index < len(module.ports) - 1 else ""
        lines.append(f"    {format_port_decl(port, mode)}{comma}")
    lines.append(");")
    return lines


def bbox_tie_ports(module: ModuleInfo) -> list[Port]:
    return [port for port in module.ports if port.direction == "o"]


def format_bbox_body(module: ModuleInfo) -> list[str]:
    output_ports = bbox_tie_ports(module)
    if not output_ports:
        return []
    lines = ["", "//output tie-off------------------------------------------------------------"]
    name_width = max(len(port.name) for port in output_ports)
    for port in output_ports:
        lines.append(f"assign {port.name:<{name_width}} = '0;")
    return lines


def format_module_dummy(module: ModuleInfo, mode: str) -> str:
    lines = [f"// Source module: {module.name}", *format_module_header(module, mode)]
    if mode == MODE_BBOX:
        lines.extend(format_bbox_body(module))
    lines.extend(["", "endmodule"])
    return "\n".join(lines)


def generate_dummy(rtl_path: Path, out_path: Path, mode: str) -> list[ModuleInfo]:
    if mode not in MODE_SET:
        raise ValueError(f"unsupported mode: {mode}")
    modules = parse_modules(rtl_path.read_text(encoding="utf-8"))
    if not modules:
        raise ValueError(f"no module found in {rtl_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n\n".join(format_module_dummy(module, mode) for module in modules) + "\n",
        encoding="utf-8",
    )
    return modules


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a dummy SystemVerilog module from RTL source."
    )
    parser.add_argument("rtl_path", help="RTL source path, absolute or relative")
    parser.add_argument(
        "-m",
        "--mode",
        choices=sorted(MODE_SET),
        default=MODE_BBOX,
        help="dummy mode, default: bbox",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="dummy.sv",
        help="output RTL path, default: dummy.sv",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    rtl_path = Path(args.rtl_path)
    if not rtl_path.is_file():
        print(f"error: RTL file not found: {rtl_path}", file=sys.stderr)
        return 1

    out_path = Path(args.output)
    if rtl_path.resolve() == out_path.resolve():
        print("error: output path must differ from RTL input path", file=sys.stderr)
        return 1

    modules = generate_dummy(rtl_path, out_path, args.mode)
    names = ", ".join(module.name for module in modules)
    print(f"generated {out_path} mode={args.mode} module(s): {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
