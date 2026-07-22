#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")
DIRECTION_SET = {"input", "output", "inout"}
NET_TYPES = {
    "wire",
    "tri",
    "tri0",
    "tri1",
    "wand",
    "wor",
    "uwire",
    "supply0",
    "supply1",
}
DATA_TYPES = {
    "logic",
    "bit",
    "byte",
    "shortint",
    "int",
    "longint",
    "integer",
    "time",
    "reg",
}
TYPE_QUALIFIERS = {"signed", "unsigned", "automatic", "static", "var", "const"}


@dataclass(frozen=True)
class Parameter:
    name: str
    default: str


@dataclass(frozen=True)
class Port:
    name: str
    direction: str
    type_text: str
    unpacked: str = ""


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    parameters: list[Parameter]
    ports: list[Port]


def strip_comments(text: str) -> str:
    result: list[str] = []
    i = 0
    in_line = False
    in_block = False
    in_string = False
    escape = False
    while i < len(text):
        char = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if in_line:
            if char == "\n":
                in_line = False
                result.append(char)
            i += 1
            continue
        if in_block:
            if char == "*" and nxt == "/":
                in_block = False
                result.append(" ")
                i += 2
            else:
                result.append("\n" if char == "\n" else " ")
                i += 1
            continue
        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            i += 1
            continue
        if char == '"':
            in_string = True
            result.append(char)
            i += 1
            continue
        if char == "/" and nxt == "/":
            in_line = True
            i += 2
            continue
        if char == "/" and nxt == "*":
            in_block = True
            result.append(" ")
            i += 2
            continue
        result.append(char)
        i += 1
    return "".join(result)


def split_top_level(text: str, sep: str = ",") -> list[str]:
    parts: list[str] = []
    start = 0
    round_depth = 0
    square_depth = 0
    brace_depth = 0
    in_string = False
    escape = False
    for idx, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "(":
            round_depth += 1
        elif char == ")":
            round_depth = max(0, round_depth - 1)
        elif char == "[":
            square_depth += 1
        elif char == "]":
            square_depth = max(0, square_depth - 1)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif (
            char == sep
            and round_depth == 0
            and square_depth == 0
            and brace_depth == 0
        ):
            part = text[start:idx].strip()
            if part:
                parts.append(part)
            start = idx + 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def split_assignment(text: str) -> tuple[str, str]:
    round_depth = square_depth = brace_depth = 0
    for idx, char in enumerate(text):
        if char == "(":
            round_depth += 1
        elif char == ")":
            round_depth = max(0, round_depth - 1)
        elif char == "[":
            square_depth += 1
        elif char == "]":
            square_depth = max(0, square_depth - 1)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif (
            char == "="
            and round_depth == 0
            and square_depth == 0
            and brace_depth == 0
        ):
            return text[:idx].strip(), text[idx + 1 :].strip()
    return text.strip(), "<must_be_specified>"


def find_matching(text: str, open_idx: int, left: str, right: str) -> int:
    depth = 0
    in_string = False
    escape = False
    for idx in range(open_idx, len(text)):
        char = text[idx]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == left:
            depth += 1
        elif char == right:
            depth -= 1
            if depth == 0:
                return idx
    raise ValueError(f"unmatched {left}")


def find_statement_end(text: str, start: int) -> int:
    round_depth = square_depth = brace_depth = 0
    for idx in range(start, len(text)):
        char = text[idx]
        if char == "(":
            round_depth += 1
        elif char == ")":
            round_depth = max(0, round_depth - 1)
        elif char == "[":
            square_depth += 1
        elif char == "]":
            square_depth = max(0, square_depth - 1)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif (
            char == ";"
            and round_depth == 0
            and square_depth == 0
            and brace_depth == 0
        ):
            return idx
    raise ValueError("missing statement semicolon")


def normalize_space(text: str) -> str:
    return " ".join(text.replace("\n", " ").replace("\t", " ").split())


def first_word(text: str) -> str:
    match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_$]*)", text)
    return match.group(1) if match else ""


def extract_declarator(text: str) -> tuple[str, str, str]:
    left, _ = split_assignment(text)
    left = left.strip()
    match = re.match(
        r"^(?P<prefix>.*?)(?P<name>[A-Za-z_][A-Za-z0-9_$]*)"
        r"\s*(?P<unpacked>(?:\[[^\]]+\]\s*)*)$",
        left,
        flags=re.S,
    )
    if not match:
        raise ValueError(f"cannot parse declarator: {text}")
    prefix = normalize_space(match.group("prefix"))
    name = match.group("name")
    unpacked = normalize_space(match.group("unpacked"))
    return prefix, name, unpacked


def parameter_from_item(item: str) -> Parameter | None:
    item = normalize_space(item)
    if not item or item.startswith("localparam"):
        return None
    if item.startswith("parameter "):
        item = item[len("parameter ") :].strip()
    left, default = split_assignment(item)
    names = IDENT_RE.findall(left)
    if not names:
        return None
    name = names[-1]
    return Parameter(name=name, default=default.rstrip(","))


def parse_parameter_items(text: str) -> list[Parameter]:
    params: list[Parameter] = []
    seen: set[str] = set()
    for item in split_top_level(text):
        param = parameter_from_item(item)
        if param and param.name not in seen:
            seen.add(param.name)
            params.append(param)
    return params


def internal_parameter_statements(body: str) -> list[str]:
    statements: list[str] = []
    for match in re.finditer(r"\b(?:localparam|parameter)\b", body):
        keyword = match.group(0)
        if keyword == "localparam":
            continue
        end = find_statement_end(body, match.end())
        statements.append(body[match.start() : end])
    return statements


def parse_decl_statement(statement: str) -> list[Port]:
    statement = normalize_space(statement.rstrip(";"))
    direction = first_word(statement)
    if direction not in DIRECTION_SET:
        return []
    remain = statement[len(direction) :].strip()
    parts = split_top_level(remain)
    ports: list[Port] = []
    current_type = ""
    for idx, part in enumerate(parts):
        prefix, name, unpacked = extract_declarator(part)
        if idx == 0 or prefix:
            current_type = prefix
        ports.append(
            Port(
                name=name,
                direction={"input": "i", "output": "o", "inout": "io"}[direction],
                type_text=current_type,
                unpacked=unpacked,
            )
        )
    return ports


def parse_ansi_ports(port_text: str) -> list[Port]:
    ports: list[Port] = []
    current_direction = ""
    current_type = ""
    for item in split_top_level(port_text):
        item = item.strip()
        if not item or item.startswith("`"):
            continue
        word = first_word(item)
        if word in DIRECTION_SET:
            for port in parse_decl_statement(item):
                current_direction = port.direction
                current_type = port.type_text
                ports.append(port)
            continue
        if item.startswith("."):
            formal = item[1:].split("(", 1)[0].strip()
            ports.append(Port(name=formal, direction="?", type_text=""))
            continue
        prefix, name, unpacked = extract_declarator(item)
        if current_direction and not prefix:
            ports.append(
                Port(
                    name=name,
                    direction=current_direction,
                    type_text=current_type,
                    unpacked=unpacked,
                )
            )
            continue
        ports.append(
            Port(
                name=name,
                direction="if" if prefix else "?",
                type_text=prefix,
                unpacked=unpacked,
            )
        )
    return ports


def formal_port_names(port_text: str) -> list[tuple[str, str]]:
    names: list[tuple[str, str]] = []
    for item in split_top_level(port_text):
        item = item.strip()
        if not item or item.startswith("`"):
            continue
        if item.startswith("."):
            formal = item[1:].split("(", 1)[0].strip()
            names.append((formal, item))
            continue
        _, name, _ = extract_declarator(item)
        names.append((name, item))
    return names


def parse_non_ansi_ports(port_text: str, body: str) -> list[Port]:
    declared: dict[str, Port] = {}
    for match in re.finditer(r"\b(input|output|inout)\b", body):
        end = find_statement_end(body, match.end())
        for port in parse_decl_statement(body[match.start() : end]):
            declared[port.name] = port
    ports: list[Port] = []
    for name, raw in formal_port_names(port_text):
        if name in declared:
            ports.append(declared[name])
            continue
        prefix, formal_name, unpacked = extract_declarator(raw)
        ports.append(
            Port(
                name=formal_name,
                direction="if" if prefix else "?",
                type_text=prefix,
                unpacked=unpacked,
            )
        )
    return ports


def parse_module_header(header: str) -> tuple[str, str, str]:
    match = re.match(r"\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)", header)
    if not match:
        raise ValueError("module name not found")
    name = match.group(1)
    idx = match.end()
    param_text = ""
    while idx < len(header) and header[idx].isspace():
        idx += 1
    if idx < len(header) and header[idx] == "#":
        idx += 1
        while idx < len(header) and header[idx].isspace():
            idx += 1
        if idx < len(header) and header[idx] == "(":
            end = find_matching(header, idx, "(", ")")
            param_text = header[idx + 1 : end]
            idx = end + 1
    while idx < len(header) and header[idx].isspace():
        idx += 1
    port_text = ""
    if idx < len(header) and header[idx] == "(":
        end = find_matching(header, idx, "(", ")")
        port_text = header[idx + 1 : end]
    return name, param_text, port_text


def parse_modules(text: str) -> list[ModuleInfo]:
    clean = strip_comments(text)
    modules: list[ModuleInfo] = []
    for match in re.finditer(r"\bmodule\b", clean):
        header_end = find_statement_end(clean, match.start())
        end_match = re.search(r"\bendmodule\b", clean[header_end:])
        if not end_match:
            raise ValueError("endmodule not found")
        body_start = header_end + 1
        body_end = header_end + end_match.start()
        header = clean[match.start() : header_end]
        body = clean[body_start:body_end]
        name, param_text, port_text = parse_module_header(header)
        params = parse_parameter_items(param_text)
        seen = {param.name for param in params}
        for statement in internal_parameter_statements(body):
            for param in parse_parameter_items(statement):
                if param.name not in seen:
                    seen.add(param.name)
                    params.append(param)
        header_ports = parse_ansi_ports(port_text)
        has_ansi_direction = any(port.direction in {"i", "o", "io"} for port in header_ports)
        if has_ansi_direction:
            ports = header_ports
        else:
            ports = parse_non_ansi_ports(port_text, body)
        modules.append(ModuleInfo(name=name, parameters=params, ports=ports))
    return modules


def signal_suffix(direction: str, port_name: str) -> str:
    if direction == "i":
        return port_name if port_name.startswith("i_") else f"i_{port_name}"
    if direction == "o":
        return port_name if port_name.startswith("o_") else f"o_{port_name}"
    if direction == "io":
        return port_name if port_name.startswith("io_") else f"io_{port_name}"
    if direction == "if":
        return port_name if port_name.startswith("if_") else f"if_{port_name}"
    return f"x_{port_name}"


def signal_name(tag: str, port: Port) -> str:
    return f"u_{tag}_{signal_suffix(port.direction, port.name)}"


def is_passthrough_port(port: Port) -> bool:
    return (
        port.direction == "i"
        and (
            port.name == "clk"
            or port.name == "rst_n"
            or port.name.endswith("_clk")
            or port.name.endswith("_rst_n")
        )
    )


def connection_name(tag: str, port: Port) -> str:
    if is_passthrough_port(port):
        return port.name
    return signal_name(tag, port)


def signal_decl_type(port: Port) -> str:
    text = normalize_space(port.type_text)
    if not text:
        return "wire"
    words = text.split()
    if words[0] in NET_TYPES:
        return text
    if words[0] == "reg":
        return "wire" + text[len("reg") :]
    if words[0] in {"signed", "unsigned"} or text.startswith("["):
        return f"wire {text}"
    if any(token in text for token in ("struct", "union", "enum", "::")):
        return text
    if words[0] in DATA_TYPES:
        return text
    if words[0] in TYPE_QUALIFIERS and len(words) > 1:
        return text
    return text


def interface_decl_type(port: Port) -> tuple[str, str]:
    text = normalize_space(port.type_text)
    if not text:
        return "interface", ""
    first = text.split()[0]
    if "." in first and "::" not in first:
        base, modport = first.split(".", 1)
        return base, modport
    return text, ""


def format_signal_declarations(module: ModuleInfo, tag: str) -> list[str]:
    lines = ["//signal declare-------------------------------------------------------------"]
    entries: list[tuple[str, str, str, str]] = []
    for port in module.ports:
        if is_passthrough_port(port):
            continue
        name = signal_name(tag, port)
        if port.direction == "if":
            decl_type, modport = interface_decl_type(port)
            comment = f" // modport: {modport}" if modport else ""
            entries.append((decl_type, name, "();", comment))
        else:
            unpacked = f" {port.unpacked}" if port.unpacked else ""
            entries.append((signal_decl_type(port), name, f"{unpacked};", ""))
    if entries:
        type_width = max(len(decl_type) for decl_type, _, _, _ in entries)
        name_width = max(len(name) for _, name, _, _ in entries)
        for decl_type, name, suffix, comment in entries:
            lines.append(f"{decl_type:<{type_width}} {name:<{name_width}}{suffix}{comment}")
    return lines


def format_input_assigns(module: ModuleInfo, tag: str) -> list[str]:
    input_ports = [
        port for port in module.ports
        if port.direction == "i" and not is_passthrough_port(port)
    ]
    if not input_ports:
        return []
    lines = ["", "//input assign---------------------------------------------------------------"]
    name_width = max(len(signal_name(tag, port)) for port in input_ports)
    for port in input_ports:
        lines.append(f"assign {signal_name(tag, port):<{name_width}} = {port.name};")
    return lines


def format_parameter_instance(module: ModuleInfo, inst_name: str) -> list[str]:
    if not module.parameters:
        return [f"{module.name} {inst_name}"]
    name_width = max(len(param.name) for param in module.parameters)
    value_width = max(len(param.name) for param in module.parameters)
    lines = [f"{module.name} #("]
    for idx, param in enumerate(module.parameters):
        comma = "," if idx < len(module.parameters) - 1 else " "
        lines.append(
            f"    .{param.name:<{name_width}} ({param.name:<{value_width}})"
            f"{comma} //default: {param.default}"
        )
    lines.append(f"){inst_name}")
    return lines


def format_port_instance(module: ModuleInfo, tag: str) -> list[str]:
    name_width = max((len(port.name) for port in module.ports), default=1)
    value_width = max(
        (len(connection_name(tag, port)) for port in module.ports),
        default=1,
    )
    lines = ["("]
    for idx, port in enumerate(module.ports):
        comma = "," if idx < len(module.ports) - 1 else " "
        lines.append(
            f"    .{port.name:<{name_width}} ({connection_name(tag, port):<{value_width}})"
            f"{comma} //{port.direction}"
        )
    lines.append(");")
    return lines


def format_module_instance(module: ModuleInfo) -> str:
    tag = "inst"
    inst_name = f"u_{module.name.lower()}_{tag}"
    lines: list[str] = [
        f"// {module.name} integration snippet",
        *format_signal_declarations(module, tag),
        *format_input_assigns(module, tag),
        "",
        "//instance-------------------------------------------------------------------",
        *format_parameter_instance(module, inst_name),
        *format_port_instance(module, tag),
    ]
    return "\n".join(lines)


def generate_inst(rtl_path: Path, out_path: Path) -> list[ModuleInfo]:
    text = rtl_path.read_text(encoding="utf-8")
    modules = parse_modules(text)
    if not modules:
        raise ValueError(f"no module found in {rtl_path}")
    snippets = [
        f"// Source: {rtl_path}",
        "",
        "\n\n".join(format_module_instance(module) for module in modules),
        "",
    ]
    out_path.write_text("\n".join(snippets), encoding="utf-8")
    return modules


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate SystemVerilog integration instance snippet."
    )
    parser.add_argument("rtl_abs_path", help="RTL absolute path")
    parser.add_argument(
        "-o",
        "--output",
        default="inst.sv",
        help="output snippet file, default: inst.sv",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    rtl_path = Path(args.rtl_abs_path)
    if not rtl_path.is_file():
        print(f"error: RTL file not found: {rtl_path}", file=sys.stderr)
        return 1
    out_path = Path(args.output)
    modules = generate_inst(rtl_path, out_path)
    names = ", ".join(module.name for module in modules)
    print(f"generated {out_path} for module(s): {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
