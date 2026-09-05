from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
import re
from typing import Iterable

from model import MEMORY_TYPES, InputFormatError, MemoryShape


_TYPE_PATTERN = "|".join(MEMORY_TYPES)
_REPORT_RE = re.compile(
    rf"^\s*"
    rf"(?P<shape>"
    rf"(?P<mem_type>{_TYPE_PATTERN})"
    rf"(?P<depth>[1-9][0-9]*)x"
    rf"(?P<width>[1-9][0-9]*)"
    rf"(?:x(?P<strb_w>[1-9][0-9]*))?"
    rf"(?:_usr(?P<mem_user>[0-9]+))?"
    rf")"
    rf"\s+(?:Info|Message|Warning):.*\s+"
    rf"(?P<hierarchy>\S+)\s*$"
)


def parse_report_line(
    line: str,
    *,
    prefix: str,
    source: Path,
    line_number: int,
) -> MemoryShape | None:
    if not line.strip():
        return None
    match = _REPORT_RE.fullmatch(line)
    if not match:
        raise InputFormatError(
            f"{source}:{line_number}: invalid memory report line: {line.rstrip()!r}"
        )
    mem_user = int(match.group("mem_user") or 0)
    return MemoryShape(
        mem_type=match.group("mem_type"),
        prefix=prefix,
        suffix=f"usr{mem_user}" if mem_user else "",
        depth=int(match.group("depth")),
        width=int(match.group("width")),
        strb_w=int(match.group("strb_w") or 1),
        mem_user=mem_user,
        hierarchy=match.group("hierarchy"),
    )


def aggregate_shapes(shapes: Iterable[MemoryShape]) -> list[MemoryShape]:
    grouped: OrderedDict[
        tuple[str, int, int, int, int, str], tuple[MemoryShape, list[str]]
    ] = OrderedDict()
    for shape in shapes:
        if shape.identity not in grouped:
            grouped[shape.identity] = (shape, [])
        grouped[shape.identity][1].append(shape.hierarchy)

    result = []
    for shape, hierarchies in grouped.values():
        result.append(
            replace(
                shape,
                instance_num=len(hierarchies),
                hierarchy=",".join(hierarchies),
            )
        )
    return result


def _parse_report_file_raw(path: Path, prefix: str) -> list[MemoryShape]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise InputFormatError(f"cannot read report file {path}: {exc}") from exc
    shapes = []
    for line_number, line in enumerate(lines, 1):
        shape = parse_report_line(
            line,
            prefix=prefix,
            source=path,
            line_number=line_number,
        )
        if shape is not None:
            shapes.append(shape)
    return shapes


def parse_report_file(path: Path, prefix: str) -> list[MemoryShape]:
    return aggregate_shapes(_parse_report_file_raw(path, prefix))


def parse_report_directory(
    work_path: Path,
    prefix: str,
) -> dict[str, list[MemoryShape]]:
    all_shapes = []
    found_file = False
    for mem_type in MEMORY_TYPES:
        report_path = work_path / f"{mem_type}.lst"
        if report_path.is_file():
            found_file = True
            all_shapes.extend(_parse_report_file_raw(report_path, prefix))
    if not found_file:
        expected = ", ".join(f"{item}.lst" for item in MEMORY_TYPES)
        raise InputFormatError(
            f"no memory report files found in {work_path}; expected {expected}"
        )

    result = {mem_type: [] for mem_type in MEMORY_TYPES}
    for shape in aggregate_shapes(all_shapes):
        result[shape.mem_type].append(shape)
    return result
