from __future__ import annotations

import keyword
import math
import re
from pathlib import Path
from typing import Any

from .models import SpecialOptions


SV_KEYWORDS = {
    "always", "and", "assign", "automatic", "begin", "bit", "break",
    "byte", "case", "class", "clocking", "const", "continue", "default",
    "disable", "do", "else", "end", "endcase", "endclass", "endfunction",
    "endmodule", "endpackage", "endtask", "enum", "event", "for", "foreach",
    "forever", "fork", "function", "generate", "genvar", "if", "import",
    "initial", "inout", "input", "int", "integer", "interface", "localparam",
    "logic", "longint", "module", "or", "output", "package", "parameter",
    "program", "property", "rand", "reg", "repeat", "return", "shortint",
    "signed", "static", "string", "struct", "task", "this", "time",
    "typedef", "union", "unsigned", "virtual", "void", "wait", "while",
    "wire",
}

C_KEYWORDS = {
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if",
    "inline", "int", "long", "register", "restrict", "return", "short",
    "signed", "sizeof", "static", "struct", "switch", "typedef", "union",
    "unsigned", "void", "volatile", "while", "_Bool", "_Complex", "_Imaginary",
}

VHDL_KEYWORDS = {
    "abs", "access", "after", "alias", "all", "and", "architecture",
    "array", "assert", "assume", "assume_guarantee", "attribute", "begin",
    "block", "body", "buffer", "bus", "case", "component", "configuration",
    "constant", "context", "cover", "default", "disconnect", "downto",
    "else", "elsif", "end", "entity", "exit", "fairness", "file", "for",
    "force", "function", "generate", "generic", "group", "guarded", "if",
    "impure", "in", "inertial", "inout", "is", "label", "library",
    "linkage", "literal", "loop", "map", "mod", "nand", "new", "next",
    "nor", "not", "null", "of", "on", "open", "or", "others", "out",
    "package", "parameter", "port", "postponed", "procedure", "process",
    "property", "protected", "pure", "range", "record", "register", "reject",
    "release", "rem", "report", "restrict", "restrict_guarantee", "return",
    "rol", "ror", "select", "sequence", "severity", "shared", "signal",
    "sla", "sll", "sra", "srl", "strong", "subtype", "then", "to",
    "transport", "type", "unaffected", "units", "until", "use", "variable",
    "view", "vmode", "vprop", "vunit", "wait", "while", "with", "xnor",
    "xor",
}

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class CSRValidationError(ValueError):
    pass


def parse_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise CSRValidationError(f"{label}: boolean is not a valid integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value).strip().replace("_", "")
    if not text:
        raise CSRValidationError(f"{label}: value is empty")
    try:
        return int(text, 0)
    except ValueError as exc:
        raise CSRValidationError(f"{label}: invalid integer '{value}'") from exc


def parse_optional_int(value: Any, label: str) -> int | None:
    if value is None or str(value).strip() in {"", "-"}:
        return None
    return parse_int(value, label)


def parse_special(value: Any, label: str) -> SpecialOptions:
    result = SpecialOptions()
    text = str(value or "").strip()
    if text in {"", "-"}:
        return result
    for raw_part in text.split(","):
        part = raw_part.strip()
        lowered = part.lower()
        if not part:
            continue
        if lowered.startswith("slv_filename="):
            result.slv_filename = part.split("=", 1)[1].strip()
        elif lowered.startswith("bytesize="):
            result.bytesize = parse_int(part.split("=", 1)[1], f"{label} bytesize")
        elif re.fullmatch(r"repeat\s+\d+", lowered):
            result.repeat = int(lowered.split()[1])
        elif re.fullmatch(r"shadow(?:\s+\d+)?", lowered):
            fields = lowered.split()
            result.shadow = int(fields[1]) if len(fields) == 2 else 1
        else:
            result.extras.append(part)
    if result.repeat < 1:
        raise CSRValidationError(f"{label}: repeat must be at least 1")
    if result.shadow < 0:
        raise CSRValidationError(f"{label}: shadow must not be negative")
    if result.bytesize is not None and result.bytesize <= 0:
        raise CSRValidationError(f"{label}: bytesize must be positive")
    return result


def validate_identifier(name: str, label: str, include_c: bool = True) -> str:
    lowered = name.strip().lower()
    if not IDENTIFIER_RE.fullmatch(lowered):
        raise CSRValidationError(
            f"{label}: '{name}' is not a valid identifier"
        )
    reserved = SV_KEYWORDS | VHDL_KEYWORDS | (
        C_KEYWORDS if include_c else set()
    )
    if lowered in reserved or keyword.iskeyword(lowered):
        raise CSRValidationError(f"{label}: '{name}' is a reserved keyword")
    return lowered


def expand_defaults(value: Any, repeat: int, width: int, label: str) -> list[int]:
    text = str(value or "").strip()
    parts = [item.strip() for item in text.split(",")] if text else ["0"]
    values = [parse_int(item or "0", label) for item in parts]
    limit = 1 << width
    for item in values:
        if item < 0 or item >= limit:
            raise CSRValidationError(
                f"{label}: value 0x{item:X} does not fit in {width} bits"
            )
    while len(values) < repeat:
        values.append(values[-1])
    if len(values) > repeat:
        raise CSRValidationError(
            f"{label}: {len(values)} defaults provided for repeat {repeat}"
        )
    return values


def clog2(value: int) -> int:
    return max(1, math.ceil(math.log2(max(2, value))))


def hex_width(bitwidth: int) -> int:
    return max(1, math.ceil(bitwidth / 4))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")
