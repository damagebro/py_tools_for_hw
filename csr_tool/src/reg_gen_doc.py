import os
import json
try:
    import jinja2
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

try:
    from .models import ModuleModel
except ImportError:
    from models import ModuleModel

class DocGenerator:
    """
    Generates documentation (HTML, JSON, Markdown) from parsed ModuleModel.
    """
    def __init__(self, module: ModuleModel, out_dir: str):
        self.module = module
        self.out_dir = out_dir

    def generate_all(self, is_nested=False):
        os.makedirs(self.out_dir, exist_ok=True)
        self.generate_markdown()
        self.generate_html(is_nested=False)
        self.generate_excel(is_nested=False)
        self.generate_json(is_nested=False)
        if is_nested:
            self.generate_tree_markdown()
            self.generate_html(is_nested=True)
            self.generate_excel(is_nested=True)
            self.generate_json(is_nested=True)

    def _build_html_address_map(self, module: ModuleModel, section_num="1", bytesize=None, depth=0):
        items = []
        base_addr = module.base_address
        if bytesize is not None:
            end_addr = base_addr + bytesize - 1
            addr_str = f"addr=0x{base_addr:08X}~0x{end_addr:08X}, bytesize=0x{bytesize:04X};"
        else:
            addr_str = f"addr=0x{base_addr:08X}~..., bytesize=unknown;"
            
        items.append({
            'depth': depth,
            'section': section_num,
            'name': module.name,
            'addr_str': addr_str
        })
        
        for i, sub in enumerate(module.sub_modules):
            sub_section = f"{section_num}.{i+1}"
            items.extend(self._build_html_address_map(sub.module_obj, sub_section, sub.bytesize, depth + 1))
            
        return items

    def _build_html_modules_data(self, module: ModuleModel, section_num="1", recurse=True):
        modules_data = []
        rows = []
        for reg in module.registers:
            if not reg.fields:
                rows.append({
                    'offset': f"0x{reg.offset:X}", 'reg_name': reg.name, 'field': '',
                    'msb': '', 'lsb': '', 'sw_access': '', 'default_value': '',
                    'reg_type': reg.reg_type, 'special': reg.special, 'description': reg.description
                })
            else:
                for i, field in enumerate(reg.fields):
                    rows.append({
                        'offset': f"0x{reg.offset:X}" if i == 0 else "",
                        'reg_name': reg.name if i == 0 else "",
                        'field': field.name,
                        'msb': str(field.msb),
                        'lsb': str(field.lsb),
                        'sw_access': field.sw_access,
                        'default_value': field.default_value,
                        'reg_type': reg.reg_type if i == 0 else "",
                        'special': reg.special if i == 0 else "",
                        'description': field.description
                    })
                    
        modules_data.append({
            'section': section_num,
            'name': module.name,
            'rows': rows
        })
        
        if recurse:
            for i, sub in enumerate(module.sub_modules):
                sub_section_num = f"{section_num}.{i+1}" if section_num else str(i+1)
                modules_data.extend(self._build_html_modules_data(sub.module_obj, sub_section_num, recurse=True))
            
        return modules_data

    def generate_html(self, is_nested=False):
        if not HAS_JINJA2:
            print("[!] 'jinja2' package not found. Skipping HTML generation.")
            print("[!] To enable HTML output, please install jinja2 (e.g., pip install jinja2).")
            return
            
        if is_nested:
            out_path = os.path.join(self.out_dir, f"{self.module.name}_reg_tree.html")
            address_map = self._build_html_address_map(self.module, bytesize=self.module.base_info.system_bytesize)
            modules_data = self._build_html_modules_data(self.module, recurse=True)
        else:
            out_path = os.path.join(self.out_dir, f"{self.module.name}_gen.html")
            address_map = []
            modules_data = self._build_html_modules_data(self.module, section_num="", recurse=False)
        
        template_str = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ module_name }} CSR Documentation</title>
    <style>
        body { font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif; margin: 20px; color: #333; line-height: 1.6; }
        h1, h2, h3 { color: #0056b3; }
        a { color: #0056b3; text-decoration: none; }
        a:hover { text-decoration: underline; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; font-size: 14px; background: #fff; }
        th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
        th { background-color: #f8f9fa; font-weight: bold; border-bottom: 2px solid #dee2e6; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        tr:hover { background-color: #f1f1f1; }
        details { margin-bottom: 15px; border: 1px solid #ddd; border-radius: 4px; padding: 5px 10px; background: #fafafa; }
        summary { font-size: 1.2em; font-weight: bold; cursor: pointer; outline: none; padding: 5px 0; }
        .address-map { background: #f8f9fa; padding: 15px; border-radius: 4px; border: 1px solid #ddd; font-family: monospace; margin-bottom: 30px; }
        .am-row { display: flex; padding: 2px 0; }
        .am-name { flex: 0 0 350px; }
        .am-addr { color: #555; }
    </style>
</head>
<body>
    <h1>Module: {{ module_name }}</h1>
    
    {% if is_nested %}
    <h2>Address Map</h2>
    <div class="address-map">
        {% for item in address_map %}
        <div class="am-row" style="margin-left: {{ item.depth * 20 }}px;">
            <div class="am-name">
                <a href="#module-{{ item.name }}">{{ item.section }} {{ item.name }}</a>
            </div>
            <div class="am-addr"># {{ item.addr_str }}</div>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    <h2>Registers</h2>
    {% for mod in modules %}
    <details open id="module-{{ mod.name }}">
        <summary>{{ mod.section }} {{ mod.name }}</summary>
        <div style="overflow-x: auto; margin-top: 10px;">
            <table>
                <thead>
                    <tr>
                        <th>offset</th><th>reg_name</th><th>field</th><th>msb</th><th>lsb</th>
                        <th>SW_access</th><th>default_value</th><th>reg_type</th><th>special</th><th>description</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in mod.rows %}
                    <tr>
                        <td>{{ row.offset }}</td><td>{{ row.reg_name }}</td><td>{{ row.field }}</td>
                        <td>{{ row.msb }}</td><td>{{ row.lsb }}</td><td>{{ row.sw_access }}</td>
                        <td>{{ row.default_value }}</td><td>{{ row.reg_type }}</td><td>{{ row.special }}</td>
                        <td>{{ row.description }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </details>
    {% endfor %}
</body>
</html>"""
        
        template = jinja2.Template(template_str)
        html_content = template.render(
            module_name=self.module.name,
            is_nested=is_nested,
            address_map=address_map,
            modules=modules_data
        )
        
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"[*] Generating HTML: {out_path}")

    def generate_json(self, is_nested=False):
        import dataclasses
        suffix = "_reg_tree" if is_nested else "_gen"
        out_path = os.path.join(self.out_dir, f"{self.module.name}{suffix}.json")
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(dataclasses.asdict(self.module), f, indent=4)
        print(f"[*] Generating JSON: {out_path}")

    def generate_excel(self, is_nested=False):
        if not HAS_OPENPYXL:
            print("[!] 'openpyxl' package not found. Skipping Excel generation.")
            print("[!] To enable Excel output, please install openpyxl (e.g., pip install openpyxl).")
            return
            
        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        header_fill = PatternFill(start_color="E9ECEF", end_color="E9ECEF", fill_type="solid")
        header_font = Font(bold=True)

        def write_module_to_sheet(ws, module: ModuleModel):
            ws.append(["# base_info"])
            ws.append(["item", "type_input"])
            ws["A2"].font = header_font
            ws["B2"].font = header_font
            ws["A2"].fill = header_fill
            ws["B2"].fill = header_fill
            
            base_rows = []
            if module.base_info.system_baseaddr is not None:
                base_rows.append(["system_baseaddr", f"0x{module.base_info.system_baseaddr:X}"])
            if module.base_info.system_bytesize is not None:
                base_rows.append(["system_bytesize", f"0x{module.base_info.system_bytesize:X}"])
            if module.base_info.system_prefix:
                base_rows.append(["system_prefix", module.base_info.system_prefix])
            base_rows.extend([
                ["reg_bitwidth", str(module.base_info.reg_bitwidth)],
                ["author", module.base_info.author],
                ["email", module.base_info.email]
            ])
            for row in base_rows:
                ws.append(row)
            
            ws.append([])
            ws.append(["# reg_define"])
            reg_headers = ["offset", "reg_name", "field", "msb", "lsb", "SW_access", "default_value", "reg_type", "special", "description"]
            ws.append(reg_headers)
            header_row_idx = ws.max_row
            for col_num in range(1, len(reg_headers) + 1):
                cell = ws.cell(row=header_row_idx, column=col_num)
                cell.font = header_font
                cell.fill = header_fill
            
            for reg in module.registers:
                if not reg.fields:
                    ws.append([f"0x{reg.offset:X}", reg.name, "", "", "", "", "", reg.reg_type, reg.special, reg.description])
                else:
                    for i, field in enumerate(reg.fields):
                        offset_str = f"0x{reg.offset:X}" if i == 0 else ""
                        reg_name_str = reg.name if i == 0 else ""
                        reg_type_str = reg.reg_type if i == 0 else ""
                        special_str = reg.special if i == 0 else ""
                        desc_str = reg.description if i == 0 else ""
                        ws.append([offset_str, reg_name_str, field.name, str(field.msb), str(field.lsb), field.sw_access, field.default_value, reg_type_str, special_str, desc_str])

        if is_nested:
            out_path = os.path.join(self.out_dir, f"{self.module.name}_reg_tree.xlsx")
            
            ws_map = wb.create_sheet(title="Address Map")
            ws_map.append(["section", "module_name", "address_range", "link"])
            for col_num in range(1, 5):
                ws_map.cell(row=1, column=col_num).font = header_font
                ws_map.cell(row=1, column=col_num).fill = header_fill

            def process_module(mod, section, bytesize, depth):
                base_sheet_name = mod.name[:31]
                sheet_name = base_sheet_name
                counter = 1
                while sheet_name in wb.sheetnames:
                    suffix = f"_{counter}"
                    sheet_name = f"{base_sheet_name[:31-len(suffix)]}{suffix}"
                    counter += 1
                
                ws_mod = wb.create_sheet(title=sheet_name)
                write_module_to_sheet(ws_mod, mod)
                
                base_addr = mod.base_address
                if bytesize is not None:
                    end_addr = base_addr + bytesize - 1
                    addr_str = f"addr=0x{base_addr:08X}~0x{end_addr:08X}, bytesize=0x{bytesize:04X};"
                else:
                    addr_str = f"addr=0x{base_addr:08X}~..., bytesize=unknown;"
                
                row_idx = ws_map.max_row + 1
                indent = "  " * depth
                ws_map.cell(row=row_idx, column=1, value=section)
                ws_map.cell(row=row_idx, column=2, value=indent + mod.name)
                ws_map.cell(row=row_idx, column=3, value=addr_str)
                
                link_cell = ws_map.cell(row=row_idx, column=4, value="Go to Sheet")
                link_cell.hyperlink = f"#'{sheet_name}'!A1"
                link_cell.font = Font(color="0000FF", underline="single")
                
                backlink_cell = ws_mod.cell(row=1, column=4, value="Back to Address Map")
                backlink_cell.hyperlink = f"#'Address Map'!A{row_idx}"
                backlink_cell.font = Font(color="0000FF", underline="single")

                for i, sub in enumerate(mod.sub_modules):
                    sub_sec = f"{section}.{i+1}"
                    process_module(sub.module_obj, sub_sec, sub.bytesize, depth + 1)

            process_module(self.module, "1", self.module.base_info.system_bytesize, 0)
        else:
            out_path = os.path.join(self.out_dir, f"{self.module.name}_gen.xlsx")
            
            ws_base = wb.create_sheet(title="base_info")
            ws_base.append(["item", "type_input"])
            ws_base["A1"].font = header_font
            ws_base["B1"].font = header_font
            ws_base["A1"].fill = header_fill
            ws_base["B1"].fill = header_fill
            
            base_rows = []
            if self.module.base_info.system_baseaddr is not None:
                base_rows.append(["system_baseaddr", f"0x{self.module.base_info.system_baseaddr:X}"])
            if self.module.base_info.system_bytesize is not None:
                base_rows.append(["system_bytesize", f"0x{self.module.base_info.system_bytesize:X}"])
            if self.module.base_info.system_prefix:
                base_rows.append(["system_prefix", self.module.base_info.system_prefix])
            base_rows.extend([
                ["reg_bitwidth", str(self.module.base_info.reg_bitwidth)],
                ["author", self.module.base_info.author],
                ["email", self.module.base_info.email]
            ])
            for row in base_rows:
                ws_base.append(row)
                
            ws_reg = wb.create_sheet(title="reg_define")
            reg_headers = ["offset", "reg_name", "field", "msb", "lsb", "SW_access", "default_value", "reg_type", "special", "description"]
            ws_reg.append(reg_headers)
            for col_num in range(1, len(reg_headers) + 1):
                cell = ws_reg.cell(row=1, column=col_num)
                cell.font = header_font
                cell.fill = header_fill
                
            for reg in self.module.registers:
                if not reg.fields:
                    ws_reg.append([f"0x{reg.offset:X}", reg.name, "", "", "", "", "", reg.reg_type, reg.special, reg.description])
                else:
                    for i, field in enumerate(reg.fields):
                        offset_str = f"0x{reg.offset:X}" if i == 0 else ""
                        reg_name_str = reg.name if i == 0 else ""
                        reg_type_str = reg.reg_type if i == 0 else ""
                        special_str = reg.special if i == 0 else ""
                        desc_str = reg.description if i == 0 else ""
                        ws_reg.append([offset_str, reg_name_str, field.name, str(field.msb), str(field.lsb), field.sw_access, field.default_value, reg_type_str, special_str, desc_str])

        wb.save(out_path)
        print(f"[*] Generating Excel: {out_path}")

    def _format_markdown_table(self, headers, rows):
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))
                else:
                    col_widths.append(len(str(cell)))
        
        lines = []
        header_str = "| " + " | ".join([f"{h:<{col_widths[i]}}" for i, h in enumerate(headers)]) + " |"
        lines.append(header_str)
        
        sep_str = "| " + " | ".join([f":{'-' * max(2, col_widths[i] - 1)}" for i in range(len(headers))]) + " |"
        lines.append(sep_str)
        
        for row in rows:
            row_str = "| " + " | ".join([f"{str(cell):<{col_widths[i]}}" if i < len(col_widths) else str(cell) for i, cell in enumerate(row)]) + " |"
            lines.append(row_str)
            
        return lines

    def generate_markdown(self):
        out_path = os.path.join(self.out_dir, f"{self.module.name}_gen.md")
        lines = []
        lines.append("# base_info\n")
        
        base_headers = ["item", "type_input"]
        base_rows = []
        if self.module.base_info.system_baseaddr is not None:
            base_rows.append(["system_baseaddr", f"0x{self.module.base_info.system_baseaddr:X}"])
        if self.module.base_info.system_bytesize is not None:
            base_rows.append(["system_bytesize", f"0x{self.module.base_info.system_bytesize:X}"])
        if self.module.base_info.system_prefix:
            base_rows.append(["system_prefix", self.module.base_info.system_prefix])
        base_rows.extend([
            ["reg_bitwidth", str(self.module.base_info.reg_bitwidth)],
            ["author", self.module.base_info.author],
            ["email", self.module.base_info.email]
        ])
        lines.extend(self._format_markdown_table(base_headers, base_rows))
        lines.append("\n# reg_define\n")

        reg_headers = ["offset", "reg_name", "field", "msb", "lsb", "SW_access", "default_value", "reg_type", "special", "description"]
        reg_rows = []
        
        for reg in self.module.registers:
            if not reg.fields:
                reg_rows.append([f"0x{reg.offset:X}", reg.name, "", "", "", "", "", reg.reg_type, reg.special, reg.description])
            else:
                for i, field in enumerate(reg.fields):
                    offset_str = f"0x{reg.offset:X}" if i == 0 else ""
                    reg_name_str = reg.name if i == 0 else ""
                    reg_type_str = reg.reg_type if i == 0 else ""
                    special_str = reg.special if i == 0 else ""
                    desc_str = reg.description if i == 0 else ""
                    
                    reg_rows.append([offset_str, reg_name_str, field.name, str(field.msb), str(field.lsb), field.sw_access, field.default_value, reg_type_str, special_str, desc_str])

        lines.extend(self._format_markdown_table(reg_headers, reg_rows))
        
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"[*] Generating Markdown: {out_path}")

    def generate_tree_markdown(self):
        out_path = os.path.join(self.out_dir, f"{self.module.name}_reg_tree.md")
        lines = []
        lines.append("# address_map\n")
        lines.append("```bash")
        lines.extend(self._build_address_map(self.module, section_num="1", bytesize=self.module.base_info.system_bytesize, depth=0))
        lines.append("```\n")
        
        lines.extend(self._build_tree_markdown(self.module, "1"))
        
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"[*] Generating Tree Markdown: {out_path}")

    def _build_address_map(self, module: ModuleModel, section_num="1", bytesize=None, depth=0):
        lines = []
        
        name_str = module.name
        
        base_addr = module.base_address
        if bytesize is not None:
            end_addr = base_addr + bytesize - 1
            addr_str = f"addr=0x{base_addr:08X}~0x{end_addr:08X},  bytesize=0x{bytesize:04X};"
        else:
            addr_str = f"addr=0x{base_addr:08X}~...,  bytesize=unknown;"
            
        indent = "  " * depth
        combined_name = f"{indent}{section_num} {name_str}"
        lines.append(f"{combined_name:<35} #{addr_str}")
        
        for i, sub in enumerate(module.sub_modules):
            sub_section = f"{section_num}.{i+1}"
            lines.extend(self._build_address_map(sub.module_obj, sub_section, sub.bytesize, depth + 1))
            
        return lines

    def _build_tree_markdown(self, module: ModuleModel, section_num="1"):
        lines = []
        lines.append(f"# {section_num} {module.name}\n")
        
        reg_headers = ["offset", "reg_name", "field", "msb", "lsb", "SW_access", "default_value", "reg_type", "special", "description"]
        reg_rows = []
        
        for reg in module.registers:
            if not reg.fields:
                reg_rows.append([f"0x{reg.offset:X}", reg.name, "", "", "", "", "", reg.reg_type, reg.special, reg.description])
            else:
                for i, field in enumerate(reg.fields):
                    offset_str = f"0x{reg.offset:X}" if i == 0 else ""
                    reg_name_str = reg.name if i == 0 else ""
                    reg_type_str = reg.reg_type if i == 0 else ""
                    special_str = reg.special if i == 0 else ""
                    desc_str = reg.description if i == 0 else ""
                    
                    reg_rows.append([offset_str, reg_name_str, field.name, str(field.msb), str(field.lsb), field.sw_access, field.default_value, reg_type_str, special_str, desc_str])
        
        if reg_rows:
            lines.extend(self._format_markdown_table(reg_headers, reg_rows))
        
        lines.append("")
        
        for i, sub in enumerate(module.sub_modules):
            sub_section_num = f"{section_num}.{i+1}"
            lines.extend(self._build_tree_markdown(sub.module_obj, sub_section_num))
            
        return lines
