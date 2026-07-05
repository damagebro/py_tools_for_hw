from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Iterable

from .models import ModuleModel, RegisterModel
from .reg_common import write_json, write_text


REG_HEADERS = [
    "offset",
    "reg_name",
    "field",
    "msb",
    "lsb",
    "SW_access",
    "default_value",
    "reg_type",
    "special",
    "description",
]


class DocGenerator:
    def __init__(self, module: ModuleModel, out_dir: str):
        self.module = module
        self.out_dir = Path(out_dir)

    def generate_all(self, is_nested: bool = False) -> list[Path]:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        generated: list[Path] = []
        modules = list(self.module.walk()) if is_nested else [
            (self.module, self.module.base_info.system_baseaddr, (self.module.name,))
        ]

        for module, _, _ in modules:
            path = self.out_dir / f"{module.name}_gen.md"
            write_text(path, self.module_markdown(module))
            generated.append(path)

        if is_nested:
            tree_md = self.out_dir / f"{self.module.name}_tree.md"
            tree_html = self.out_dir / f"{self.module.name}_tree.html"
            write_text(tree_md, self.tree_markdown())
            write_text(tree_html, self.tree_html())
            generated.extend([tree_md, tree_html])
            excel = self._write_tree_excel()
        else:
            excel = self._write_module_excel(self.module)
        if excel is not None:
            generated.append(excel)

        source_suffix = Path(self.module.source_path).suffix.lower()
        if source_suffix == ".json":
            json_path = self.out_dir / (
                f"{self.module.name}_tree.json"
                if is_nested else f"{self.module.name}_gen.json"
            )
            write_json(json_path, self.module.to_dict())
            generated.append(json_path)
        return generated

    def module_markdown(self, module: ModuleModel) -> str:
        base = module.base_info
        base_rows = [
            ["reg_bitwidth", str(base.reg_bitwidth), "-"],
            ["system_baseaddr", f"0x{base.system_baseaddr:X}", "-"],
        ]
        if base.system_bytesize is not None:
            base_rows.append(["system_bytesize", f"0x{base.system_bytesize:X}", "-"])
        if base.system_prefix:
            base_rows.append(["system_prefix", base.system_prefix, "-"])
        if base.author:
            base_rows.append(["author", base.author, "-"])
        if base.email:
            base_rows.append(["email", base.email, "-"])
        base_rows.extend([key, value, "-"] for key, value in base.extras.items())

        parts = [
            "# base_info",
            "",
            self._markdown_table(["item", "type_input", "description"], base_rows),
            "",
            "# reg_define",
            "",
            self._markdown_table(REG_HEADERS, self._register_rows(module)),
        ]
        return "\n".join(parts)

    def tree_markdown(self) -> str:
        lines = [
            f"# {self.module.name} Register Tree",
            "",
            "## Address Map",
            "",
            self._markdown_table(
                ["path", "base_address", "bytesize", "source"],
                [
                    [
                        "/".join(path),
                        f"0x{base:X}",
                        f"0x{module.local_size:X}",
                        Path(module.source_path).name,
                    ]
                    for module, base, path in self.module.walk()
                ],
            ),
        ]
        for index, (module, base, path) in enumerate(self.module.walk(), start=1):
            lines.extend([
                "",
                f"## {index}. {'/'.join(path)}",
                "",
                f"- Base address: `0x{base:X}`",
                f"- Source: `{Path(module.source_path).name}`",
                "",
                self._markdown_table(REG_HEADERS, self._register_rows(module)),
            ])
        return "\n".join(lines)

    def tree_html(self) -> str:
        address_rows = []
        sections = []
        for index, (module, base, path) in enumerate(self.module.walk(), start=1):
            anchor = f"module-{index}"
            address_rows.append([
                f'<a href="#{anchor}">{html.escape("/".join(path))}</a>',
                f"0x{base:X}",
                f"0x{module.local_size:X}",
                html.escape(Path(module.source_path).name),
            ])
            sections.append(
                f'<details id="{anchor}" open>'
                f"<summary>{index}. {html.escape('/'.join(path))} "
                f"<code>0x{base:X}</code></summary>"
                f"{self._html_table(REG_HEADERS, self._register_rows(module))}"
                "</details>"
            )
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(self.module.name)} register tree</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #202124; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
th, td {{ border: 1px solid #c9ced6; padding: 7px 9px; text-align: left; }}
th {{ background: #eef2f6; position: sticky; top: 0; }}
tr:nth-child(even) {{ background: #f8fafc; }}
details {{ border-top: 1px solid #c9ced6; padding: 12px 0; }}
summary {{ cursor: pointer; font-size: 18px; font-weight: 600; }}
code {{ color: #14532d; }}
</style>
</head>
<body>
<h1>{html.escape(self.module.name)} Register Tree</h1>
<h2>Address Map</h2>
{self._html_table(["path", "base_address", "bytesize", "source"], address_rows, raw=True)}
{''.join(sections)}
</body>
</html>"""

    def _register_rows(self, module: ModuleModel) -> list[list[str]]:
        rows: list[list[str]] = []
        for reg in module.registers:
            if not reg.fields:
                rows.append([
                    f"0x{reg.offset:X}",
                    reg.name,
                    "",
                    "",
                    "",
                    "",
                    "",
                    reg.reg_type,
                    reg.special.to_text(),
                    reg.description,
                ])
                continue
            for field_index, field in enumerate(reg.fields):
                first = field_index == 0
                rows.append([
                    f"0x{reg.offset:X}" if first else "",
                    reg.name if first else "",
                    field.name,
                    str(field.msb),
                    str(field.lsb),
                    reg.sw_access if first else "",
                    field.default_value,
                    reg.reg_type if first else "",
                    reg.special.to_text() if first else "",
                    field.description or (reg.description if first else ""),
                ])
        return rows

    def _write_module_excel(self, module: ModuleModel) -> Path | None:
        try:
            import openpyxl
        except ImportError:
            print("[Warning] openpyxl is unavailable; skipping Excel output")
            return None
        path = self.out_dir / f"{module.name}_gen.xlsx"
        workbook = openpyxl.Workbook()
        base_sheet = workbook.active
        base_sheet.title = "base_info"
        base_sheet.append(["item", "type_input", "description"])
        base = module.base_info
        base_sheet.append(["reg_bitwidth", base.reg_bitwidth, "-"])
        base_sheet.append(["system_baseaddr", f"0x{base.system_baseaddr:X}", "-"])
        if base.system_bytesize is not None:
            base_sheet.append(["system_bytesize", f"0x{base.system_bytesize:X}", "-"])
        if base.system_prefix:
            base_sheet.append(["system_prefix", base.system_prefix, "-"])
        if base.author:
            base_sheet.append(["author", base.author, "-"])
        if base.email:
            base_sheet.append(["email", base.email, "-"])
        reg_sheet = workbook.create_sheet("reg_define")
        reg_sheet.append(REG_HEADERS)
        for row in self._register_rows(module):
            reg_sheet.append(row)
        self._style_workbook(workbook)
        workbook.save(path)
        return path

    def _write_tree_excel(self) -> Path | None:
        try:
            import openpyxl
        except ImportError:
            print("[Warning] openpyxl is unavailable; skipping Excel output")
            return None
        path = self.out_dir / f"{self.module.name}_tree.xlsx"
        workbook = openpyxl.Workbook()
        map_sheet = workbook.active
        map_sheet.title = "address_map"
        map_sheet.append(["path", "base_address", "bytesize", "source", "link"])
        used_names = {"address_map"}
        for index, (module, base, tree_path) in enumerate(self.module.walk(), start=1):
            sheet_name = self._unique_sheet_name(
                f"{index}_{module.name}", used_names
            )
            sheet = workbook.create_sheet(sheet_name)
            sheet.append(REG_HEADERS)
            for row in self._register_rows(module):
                sheet.append(row)
            map_sheet.append([
                "/".join(tree_path),
                f"0x{base:X}",
                f"0x{module.local_size:X}",
                Path(module.source_path).name,
                f"Open {sheet_name}",
            ])
            map_sheet.cell(map_sheet.max_row, 5).hyperlink = f"#'{sheet_name}'!A1"
            map_sheet.cell(map_sheet.max_row, 5).style = "Hyperlink"
        self._style_workbook(workbook)
        workbook.save(path)
        return path

    @staticmethod
    def _style_workbook(workbook: object) -> None:
        from openpyxl.styles import Font, PatternFill

        for sheet in workbook.worksheets:
            for cell in sheet[1]:
                cell.font = Font(bold=True)
                cell.fill = PatternFill("solid", fgColor="DCE6F1")
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                width = min(48, max(10, max(len(str(cell.value or "")) for cell in column) + 2))
                sheet.column_dimensions[column[0].column_letter].width = width

    @staticmethod
    def _unique_sheet_name(name: str, used: set[str]) -> str:
        base = name[:31]
        candidate = base
        suffix = 1
        while candidate in used:
            tail = f"_{suffix}"
            candidate = base[: 31 - len(tail)] + tail
            suffix += 1
        used.add(candidate)
        return candidate

    @staticmethod
    def _markdown_table(headers: list[str], rows: Iterable[list[str]]) -> str:
        rows_list = [[str(item) for item in row] for row in rows]
        widths = [
            max(len(headers[index]), *(len(row[index]) for row in rows_list))
            for index in range(len(headers))
        ]
        def line(values: list[str]) -> str:
            return "| " + " | ".join(
                values[index].ljust(widths[index])
                for index in range(len(headers))
            ) + " |"
        return "\n".join([
            line(headers),
            "| " + " | ".join("-" * width for width in widths) + " |",
            *(line(row) for row in rows_list),
        ])

    @staticmethod
    def _html_table(
        headers: list[str], rows: Iterable[list[str]], raw: bool = False
    ) -> str:
        def cell(value: str) -> str:
            return str(value) if raw else html.escape(str(value))
        head = "".join(f"<th>{html.escape(item)}</th>" for item in headers)
        body = "".join(
            "<tr>" + "".join(f"<td>{cell(item)}</td>" for item in row) + "</tr>"
            for row in rows
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
