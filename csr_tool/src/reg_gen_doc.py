from __future__ import annotations

import html
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from .models import ModuleModel, RegisterModel
from .reg_common import write_text


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

TREE_REG_HEADERS = ["address", *REG_HEADERS[1:]]


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
        nodes = self._document_nodes()
        lines = [
            f"# {self.module.name} Register Tree",
            "",
            "## Address Map",
            "",
            self._markdown_table(
                ["block", "address_range", "bytesize"],
                [
                    [
                        f"{section_number} {display_name}",
                        self._address_range(base, size),
                        f"0x{size:X}",
                    ]
                    for module, base, _, size, section_number, display_name in nodes
                ],
            ),
        ]
        for module, base, _, _, section_number, display_name in nodes:
            lines.extend([
                "",
                f"## {section_number} {display_name}",
                "",
                self._markdown_table(
                    TREE_REG_HEADERS,
                    self._tree_register_rows(module, base),
                ),
            ])
        return "\n".join(lines)

    def tree_html(self) -> str:
        nodes = self._document_nodes()
        address_rows = []
        sections = []
        navigation = [
            '<a class="nav-address" href="#address-map">Address Map</a>'
        ]
        for module, base, path, size, section_number, display_name in nodes:
            anchor = f"module-{section_number.replace('.', '-')}"
            address_rows.append([
                f'<a href="#{anchor}">{section_number} '
                f"{html.escape(display_name)}</a>",
                self._address_range(base, size),
                f"0x{size:X}",
            ])
            register_links = "".join(
                f'<a class="nav-register" '
                f'href="#{anchor}-reg-{reg_index}">'
                f"{html.escape(reg.name)} "
                f"(0x{base + reg.offset:X})</a>"
                for reg_index, reg in enumerate(module.registers, start=1)
            )
            navigation.append(
                f'<details class="nav-module-group" '
                f'style="--depth:{len(path) - 1}">'
                f'<summary class="nav-module">'
                f"{section_number} {html.escape(display_name)}</summary>"
                f'<div class="nav-registers">'
                f"{register_links}</div>"
                "</details>"
            )
            sections.append(
                f'<details id="{anchor}" open>'
                f"<summary>{section_number} "
                f"{html.escape(display_name)}</summary>"
                f"{self._html_register_tables(module, anchor, base)}"
                "</details>"
            )
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(self.module.name)} register tree</title>
<style>
html {{ scroll-behavior: smooth; }}
body {{ font-family: Arial, sans-serif; margin: 0; color: #202124; }}
.page-shell {{
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  width: 100%;
  min-width: 0;
  min-height: 100vh;
  transition: grid-template-columns 160ms ease;
}}
.page-shell.sidebar-collapsed {{ grid-template-columns: 52px minmax(0, 1fr); }}
.sidebar {{
  position: sticky;
  top: 0;
  height: 100vh;
  min-width: 0;
  box-sizing: border-box;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 20px 16px;
  background: #f3f5f7;
  border-right: 1px solid #c9ced6;
}}
.sidebar-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }}
.sidebar-title {{ font-size: 18px; font-weight: 700; white-space: nowrap; }}
.sidebar-toggle {{
  display: inline-flex;
  flex: 0 0 34px;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  padding: 0;
  background: #fff;
  border: 1px solid #aeb6bf;
  border-radius: 4px;
  cursor: pointer;
}}
.sidebar-toggle:hover {{ background: #e3e8ed; }}
.toggle-icon {{ position: relative; width: 16px; height: 14px; }}
.toggle-icon span {{
  position: absolute;
  left: 0;
  width: 16px;
  height: 2px;
  background: #26384a;
  transition: transform 160ms ease, opacity 160ms ease, top 160ms ease;
}}
.toggle-icon span:nth-child(1) {{ top: 1px; }}
.toggle-icon span:nth-child(2) {{ top: 6px; }}
.toggle-icon span:nth-child(3) {{ top: 11px; }}
.page-shell:not(.sidebar-collapsed) .toggle-icon span:nth-child(1) {{
  top: 6px;
  transform: rotate(45deg);
}}
.page-shell:not(.sidebar-collapsed) .toggle-icon span:nth-child(2) {{ opacity: 0; }}
.page-shell:not(.sidebar-collapsed) .toggle-icon span:nth-child(3) {{
  top: 6px;
  transform: rotate(-45deg);
}}
.page-shell.sidebar-collapsed .sidebar {{ padding: 10px 8px; }}
.page-shell.sidebar-collapsed .sidebar-title,
.page-shell.sidebar-collapsed .sidebar nav {{ display: none; }}
.sidebar nav {{ display: flex; flex-direction: column; min-width: 0; gap: 2px; }}
.sidebar a {{
  display: block;
  color: #26384a;
  padding: 6px 8px;
  text-decoration: none;
  border-left: 3px solid transparent;
}}
.sidebar a:hover {{ background: #e3e8ed; border-left-color: #4b6478; }}
.nav-address {{ font-weight: 700; }}
.nav-module-group {{ margin-left: calc(var(--depth) * 10px); }}
.nav-module-group > summary {{
  cursor: pointer;
  color: #26384a;
  font-weight: 600;
}}
.nav-module-group > summary::marker {{ color: #647789; }}
.nav-module {{ padding: 6px 8px; font-weight: 600; }}
.nav-registers {{ margin-left: 12px; }}
.nav-register {{ font-family: Consolas, monospace; font-size: 13px; }}
.content {{ min-width: 0; padding: 24px 28px; }}
.table-scroll {{ max-width: 100%; overflow-x: auto; }}
.address-table {{ table-layout: fixed; width: 90ch; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
th, td {{ border: 1px solid #c9ced6; padding: 7px 9px; text-align: left; }}
th {{ background: #eef2f6; position: sticky; top: 0; }}
tr:nth-child(even) {{ background: #f8fafc; }}
.content > details {{
  border-top: 1px solid #c9ced6;
  padding: 12px 0;
  overflow-x: auto;
}}
.content > details > summary {{ cursor: pointer; font-size: 18px; font-weight: 600; }}
code {{ color: #14532d; }}
.register-table {{ table-layout: fixed; width: 120ch; margin: 16px 0 28px; }}
.register-section {{ margin: 16px 0 28px; }}
.register-title {{ margin: 0 0 8px; font-size: 16px; font-weight: 700; }}
.register-section .register-table {{ margin: 0; }}
.register-table th {{ background: #b8b8b8; position: static; font-weight: 700; }}
.register-table td {{ background: #fff; vertical-align: top; }}
.register-table .field-description {{ white-space: pre-wrap; }}
.content > details, #address-map {{ scroll-margin-top: 16px; }}
.register-table {{ scroll-margin-top: 16px; }}
@media (max-width: 900px) {{
  .page-shell {{ grid-template-columns: 1fr; }}
  .page-shell.sidebar-collapsed {{ grid-template-columns: 1fr; }}
  .sidebar {{
    position: sticky;
    z-index: 10;
    height: auto;
    max-height: 38vh;
    border-right: 0;
    border-bottom: 1px solid #c9ced6;
  }}
  .sidebar nav {{ width: 100%; flex-direction: row; overflow-x: auto; }}
  .nav-module-group {{ margin-left: 0; flex: 0 0 auto; }}
  .nav-registers {{ display: none; }}
  .content {{ padding: 18px 16px; }}
}}
</style>
</head>
<body>
<div class="page-shell sidebar-collapsed">
<aside class="sidebar">
<div class="sidebar-header">
<button class="sidebar-toggle" type="button" data-testid="sidebar-toggle"
        aria-label="Expand navigation" title="Expand navigation">
<span class="toggle-icon" aria-hidden="true">
<span></span><span></span><span></span>
</span>
</button>
<div class="sidebar-title">{html.escape(self.module.name)} Register Tree</div>
</div>
<nav>{''.join(navigation)}</nav>
</aside>
<main class="content">
<h1>{html.escape(self.module.name)} Register Tree</h1>
<h2 id="address-map">Address Map</h2>
<div class="table-scroll">
{self._html_table(
    ["block", "address_range", "bytesize"],
    address_rows,
    raw=True,
    table_class="address-table",
    column_widths=["30ch", "30ch", "30ch"],
)}
</div>
{''.join(sections)}
</main>
</div>
<script>
(function () {{
  var shell = document.querySelector(".page-shell");
  var button = document.querySelector(".sidebar-toggle");
  function updateButton() {{
    var collapsed = shell.classList.contains("sidebar-collapsed");
    var label = collapsed ? "Expand navigation" : "Collapse navigation";
    button.setAttribute("aria-label", label);
    button.setAttribute("title", label);
  }}
  button.addEventListener("click", function () {{
    shell.classList.toggle("sidebar-collapsed");
    updateButton();
  }});
  updateButton();
}}());
</script>
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

    def _tree_register_rows(
        self,
        module: ModuleModel,
        absolute_base: int,
    ) -> list[list[str]]:
        rows = self._register_rows(module)
        for row in rows:
            if row[0]:
                row[0] = f"0x{absolute_base + int(row[0], 0):X}"
        return rows

    def _html_register_tables(
        self,
        module: ModuleModel,
        module_anchor: str,
        absolute_base: int,
    ) -> str:
        tables: list[str] = []
        for reg_index, reg in enumerate(module.registers, start=1):
            rows = [
                "<tr>"
                '<th class="meta-label">reg_name</th>'
                f'<td class="meta-value">{html.escape(reg.name)}</td>'
                '<th class="meta-label">address</th>'
                f'<td class="meta-value">'
                f"0x{absolute_base + reg.offset:X}</td>"
                "</tr>",
                "<tr>"
                '<th class="meta-label">reg_type</th>'
                f'<td class="meta-value">{html.escape(reg.reg_type)}</td>'
                '<th class="meta-label">special</th>'
                f'<td class="meta-value">'
                f"{html.escape(reg.special.to_text())}</td>"
                "</tr>",
                "<tr>"
                '<th class="meta-label">SW_access</th>'
                f'<td class="meta-value" colspan="3">'
                f"{html.escape(reg.sw_access or '-')}</td>"
                "</tr>",
            ]
            if reg.fields:
                rows.append(
                    "<tr>"
                    '<th class="field-name">field</th>'
                    '<th class="field-bit">bit_scope</th>'
                    '<th class="field-default">default_value</th>'
                    '<th class="field-description">description</th>'
                    "</tr>"
                )
                for field in reg.fields:
                    rows.append(
                        "<tr>"
                        f'<td class="field-name">{html.escape(field.name)}</td>'
                        f'<td class="field-bit">[{field.msb}:{field.lsb}]</td>'
                        f'<td class="field-default">'
                        f"{html.escape(field.default_value)}</td>"
                        f'<td class="field-description">'
                        f"{html.escape(field.description or reg.description)}</td>"
                        "</tr>"
                    )
            tables.append(
                '<section class="register-section">'
                f'<h3 class="register-title" '
                f'id="{module_anchor}-reg-{reg_index}">'
                f"{html.escape(reg.name)} "
                f"(0x{absolute_base + reg.offset:X})</h3>"
                f'<table class="register-table" '
                f'data-register="{html.escape(reg.name)}">'
                "<colgroup>"
                '<col style="width:20ch">'
                '<col style="width:20ch">'
                '<col style="width:20ch">'
                '<col style="width:60ch">'
                "</colgroup>"
                f"<tbody>{''.join(rows)}</tbody></table>"
                "</section>"
            )
        return "".join(tables)

    def _document_nodes(
        self,
    ) -> list[tuple[ModuleModel, int, tuple[str, ...], int, str, str]]:
        raw_nodes: list[
            tuple[ModuleModel, int, tuple[str, ...], int, str]
        ] = []

        def visit(
            module: ModuleModel,
            absolute_base: int,
            path: tuple[str, ...],
            allocated_size: int,
            section_parts: tuple[int, ...],
        ) -> None:
            current_path = path + (module.name,)
            section_number = ".".join(str(item) for item in section_parts)
            raw_nodes.append(
                (
                    module,
                    absolute_base,
                    current_path,
                    allocated_size,
                    section_number,
                )
            )
            for child_index, child in enumerate(module.sub_modules, start=1):
                visit(
                    child.module_obj,
                    absolute_base + child.offset,
                    current_path,
                    child.bytesize,
                    section_parts + (child_index,),
                )

        root_size = self.module.base_info.system_bytesize or self.module.local_size
        visit(
            self.module,
            self.module.base_info.system_baseaddr,
            (),
            root_size,
            (1,),
        )
        name_counts = Counter(module.name for module, _, _, _, _ in raw_nodes)
        name_indexes: defaultdict[str, int] = defaultdict(int)
        nodes = []
        for module, base, path, size, section_number in raw_nodes:
            name_indexes[module.name] += 1
            display_name = module.name
            if name_counts[module.name] > 1:
                display_name = f"{module.name}_u{name_indexes[module.name]}"
            nodes.append(
                (
                    module,
                    base,
                    path,
                    size,
                    section_number,
                    display_name,
                )
            )
        return nodes

    @staticmethod
    def _address_range(start: int, size: int) -> str:
        end = start + max(1, size) - 1
        return f"0x{start:X} ~ 0x{end:X}"

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
        map_sheet.append(["block", "address_range", "bytesize", "link"])
        used_names = {"address_map"}
        for (
            module,
            base,
            _,
            size,
            section_number,
            display_name,
        ) in self._document_nodes():
            sheet_name = self._unique_sheet_name(
                f"{section_number.replace('.', '_')}_{display_name}",
                used_names,
            )
            sheet = workbook.create_sheet(sheet_name)
            sheet.append(TREE_REG_HEADERS)
            for row in self._tree_register_rows(module, base):
                sheet.append(row)
            map_sheet.append([
                f"{section_number} {display_name}",
                self._address_range(base, size),
                f"0x{size:X}",
                f"Open {sheet_name}",
            ])
            map_sheet.cell(map_sheet.max_row, 4).hyperlink = f"#'{sheet_name}'!A1"
            map_sheet.cell(map_sheet.max_row, 4).style = "Hyperlink"
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
        headers: list[str],
        rows: Iterable[list[str]],
        raw: bool = False,
        table_class: str = "",
        column_widths: list[str] | None = None,
    ) -> str:
        def cell(value: str) -> str:
            return str(value) if raw else html.escape(str(value))
        head = "".join(f"<th>{html.escape(item)}</th>" for item in headers)
        body = "".join(
            "<tr>" + "".join(f"<td>{cell(item)}</td>" for item in row) + "</tr>"
            for row in rows
        )
        class_attr = (
            f' class="{html.escape(table_class)}"' if table_class else ""
        )
        colgroup = ""
        if column_widths:
            colgroup = "<colgroup>" + "".join(
                f'<col style="width:{html.escape(width)}">'
                for width in column_widths
            ) + "</colgroup>"
        return (
            f"<table{class_attr}>{colgroup}<thead><tr>{head}</tr></thead>"
            f"<tbody>{body}</tbody></table>"
        )
