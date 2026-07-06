from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class BaseInfoModel:
    reg_bitwidth: int = 32
    system_baseaddr: int = 0
    system_bytesize: int | None = None
    system_prefix: str = ""
    author: str = ""
    email: str = ""
    extras: dict[str, str] = field(default_factory=dict)


@dataclass
class SpecialOptions:
    repeat: int = 1
    shadow: int = 0
    bytesize: int | None = None
    slv_filename: str = ""
    extras: list[str] = field(default_factory=list)

    @property
    def has_shadow(self) -> bool:
        return self.shadow > 0

    def to_text(self) -> str:
        parts: list[str] = []
        if self.slv_filename:
            parts.append(f"slv_filename={self.slv_filename}")
        if self.bytesize is not None:
            parts.append(f"bytesize=0x{self.bytesize:X}")
        if self.repeat > 1:
            parts.append(f"repeat {self.repeat}")
        if self.shadow > 0:
            parts.append("shadow" if self.shadow == 1 else f"shadow {self.shadow}")
        parts.extend(self.extras)
        return ", ".join(parts) if parts else "-"


@dataclass
class FieldModel:
    name: str
    msb: int
    lsb: int
    sw_access: str
    default_values: list[int] = field(default_factory=lambda: [0])
    description: str = ""

    @property
    def width(self) -> int:
        return self.msb - self.lsb + 1

    @property
    def default_value(self) -> str:
        return ",".join(f"0x{value:X}" for value in self.default_values)

    def default_for(self, index: int) -> int:
        return self.default_values[min(index, len(self.default_values) - 1)]


@dataclass
class RegisterModel:
    name: str
    raw_name: str
    offset: int
    reg_type: str
    sw_access: str
    special: SpecialOptions = field(default_factory=SpecialOptions)
    description: str = ""
    fields: list[FieldModel] = field(default_factory=list)
    source_row: int = 0

    @property
    def repeat(self) -> int:
        return self.special.repeat

    def byte_size(self, word_bytes: int) -> int:
        if self.reg_type in {"slave", "mem"}:
            return self.special.bytesize or 0
        return word_bytes * self.repeat

    def default_word(self, index: int = 0) -> int:
        value = 0
        for item in self.fields:
            mask = (1 << item.width) - 1
            value |= (item.default_for(index) & mask) << item.lsb
        return value


@dataclass
class SubModuleNode:
    instance_name: str
    offset: int
    bytesize: int
    source_path: str
    module_obj: ModuleModel


@dataclass
class ModuleModel:
    name: str
    source_path: str
    base_info: BaseInfoModel = field(default_factory=BaseInfoModel)
    registers: list[RegisterModel] = field(default_factory=list)
    sub_modules: list[SubModuleNode] = field(default_factory=list)

    @property
    def word_bytes(self) -> int:
        return self.base_info.reg_bitwidth // 8

    @property
    def local_size(self) -> int:
        if not self.registers:
            return 0
        return max(reg.offset + reg.byte_size(self.word_bytes) for reg in self.registers)

    def register_by_name(self, name: str) -> RegisterModel:
        return next(reg for reg in self.registers if reg.name == name)

    def walk(
        self,
        absolute_base: int | None = None,
        path: tuple[str, ...] = (),
    ) -> Iterator[tuple[ModuleModel, int, tuple[str, ...]]]:
        if absolute_base is None:
            absolute_base = self.base_info.system_baseaddr
        current_path = path + (self.name,)
        yield self, absolute_base, current_path
        for node in self.sub_modules:
            yield from node.module_obj.walk(
                absolute_base + node.offset,
                current_path,
            )

    @staticmethod
    def clean_name(path: str) -> str:
        stem = Path(path).stem.lower()
        for suffix in ("_register", "_reg"):
            if stem.endswith(suffix):
                return stem[: -len(suffix)]
        return stem


# Compatibility aliases used by earlier extensions.
BaseInfo = BaseInfoModel
SubModuleInstance = SubModuleNode
