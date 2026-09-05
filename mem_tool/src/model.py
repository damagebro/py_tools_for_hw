from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


MEMORY_TYPES = ("spram", "tpram1ck", "tpram2ck", "sprom")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class MemToolError(RuntimeError):
    pass


class InputFormatError(MemToolError):
    pass


def validate_identifier(value: str, field_name: str) -> str:
    if not value or not _IDENTIFIER_RE.fullmatch(value):
        raise InputFormatError(
            f"{field_name} must be a valid SystemVerilog identifier: {value!r}"
        )
    return value


def parse_int(value: Any, field_name: str, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise InputFormatError(f"{field_name} must be an integer, got {value!r}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise InputFormatError(
            f"{field_name} must be an integer, got {value!r}"
        ) from exc
    if isinstance(value, float) and not value.is_integer():
        raise InputFormatError(f"{field_name} must be an integer, got {value!r}")
    if parsed < minimum:
        raise InputFormatError(
            f"{field_name} must be >= {minimum}, got {parsed}"
        )
    return parsed


@dataclass(slots=True)
class MemoryShape:
    mem_type: str
    prefix: str
    depth: int
    width: int
    strb_w: int = 1
    mem_user: int = 0
    suffix: str = ""
    instance_num: int = 1
    hierarchy: str = ""
    wr_clk_mhz: int | float | None = None
    rd_clk_mhz: int | float | None = None
    ppa_target: Any = 0

    def __post_init__(self) -> None:
        if self.mem_type not in MEMORY_TYPES:
            raise InputFormatError(
                f"unsupported memory type {self.mem_type!r}; "
                f"expected one of {MEMORY_TYPES}"
            )
        validate_identifier(self.prefix, "prefix")
        if self.suffix:
            validate_identifier(self.suffix, "suffix")
        self.depth = parse_int(self.depth, "depth", 1)
        self.width = parse_int(self.width, "width", 1)
        self.strb_w = parse_int(self.strb_w, "strb_w", 1)
        self.mem_user = parse_int(self.mem_user, "mem_user", 0)
        self.instance_num = parse_int(self.instance_num, "instance_num", 1)
        if self.mem_type == "sprom" and self.strb_w != 1:
            raise InputFormatError("sprom does not support write strobes")
        if self.width % self.strb_w:
            raise InputFormatError(
                f"width ({self.width}) must be divisible by strb_w ({self.strb_w})"
            )

    @property
    def raw_shape(self) -> str:
        value = f"{self.mem_type}{self.depth}x{self.width}"
        if self.strb_w > 1:
            value += f"x{self.strb_w}"
        if self.mem_user:
            value += f"_usr{self.mem_user}"
        return value

    @property
    def shape_name(self) -> str:
        value = f"{self.depth}x{self.width}"
        if self.strb_w > 1:
            value += f"x{self.strb_w}"
        return value

    @property
    def wrapper_name(self) -> str:
        suffix = f"_{self.suffix}" if self.suffix else ""
        return f"{self.prefix}_{self.mem_type}_{self.shape_name}{suffix}_wrapper"

    @property
    def capacity_kib(self) -> float:
        return self.depth * self.width * self.instance_num / 8 / 1024

    @property
    def identity(self) -> tuple[str, int, int, int, int, str]:
        return (
            self.mem_type,
            self.depth,
            self.width,
            self.strb_w,
            self.mem_user,
            self.suffix,
        )

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "MemoryShape":
        mem_type = str(values.get("mem_type") or "").strip()
        prefix = str(values.get("prefix") or "").strip()
        suffix = str(values.get("suffix") or "").strip()
        return cls(
            mem_type=mem_type,
            prefix=prefix,
            suffix=suffix,
            depth=values.get("depth"),
            width=values.get("width"),
            strb_w=values.get("strb_w", 1),
            mem_user=values.get("mem_user", 0),
            instance_num=values.get("instance_num", 1),
            hierarchy=str(values.get("hierarchy") or ""),
            wr_clk_mhz=values.get("wr_clk_mhz"),
            rd_clk_mhz=values.get("rd_clk_mhz"),
            ppa_target=values.get("ppa_target", 0),
        )
