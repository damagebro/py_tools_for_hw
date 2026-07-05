import os
from typing import Dict, List, Any
try:
    from .models import ModuleModel, RegisterModel, FieldModel, SubModuleInstance, BaseInfo
except ImportError:
    from models import ModuleModel, RegisterModel, FieldModel, SubModuleInstance, BaseInfo

class CSRParser:
    """
    Parses Markdown-based register definitions without external dependencies.
    Supports Single Module and Nested (Recursive) modes.
    Enforces Rule 7 (monotonically increasing offsets) and Rule 8 (bytesize limits).
    """
    def __init__(self, root_excel: str, nested: bool = False):
        self.root_excel = os.path.abspath(root_excel)
        self.nested = nested
        self.module_cache: Dict[str, ModuleModel] = {}

    def parse(self, file_path: str = None, base_addr: int = 0, max_bytesize: int = None) -> ModuleModel:
        if file_path is None:
            file_path = self.root_excel
        
        print(f"[*] Parsing Markdown: {file_path} (Base: {hex(base_addr)})")
        
        module = self._parse_markdown(file_path, base_addr, max_bytesize)
        
        # Rule 8 check: Ensure sub-module doesn't exceed allocated bytesize
        if max_bytesize is not None and module.registers:
            last_reg = module.registers[-1]
            repeat_count = 1
            for part in last_reg.special.split(','):
                part = part.strip()
                if part.startswith('repeat'):
                    try:
                        repeat_count = int(part.split()[1])
                    except ValueError:
                        pass
            
            # The total size used by this module
            total_size_used = (last_reg.offset - base_addr) + (repeat_count * (module.base_info.reg_bitwidth // 8))
            if total_size_used > max_bytesize:
                error_msg = (
                    f"Address Space Exceeded Error in {module.name}:\n"
                    f"  Total size used ({hex(total_size_used)}) exceeds allocated bytesize ({hex(max_bytesize)}).\n"
                    f"  Last register info:\n"
                    f"    reg_name: {last_reg.name}\n"
                    f"    offset: {hex(last_reg.offset - base_addr)}\n"
                    f"    reg_type: {last_reg.reg_type}\n"
                    f"    special: {last_reg.special}\n"
                )
                raise ValueError(error_msg)
                
        return module

    def _read_excel_to_md(self, file_path: str) -> List[str]:
        try:
            import openpyxl
        except ImportError:
            raise ImportError("openpyxl is required to parse .xlsx files. Please install it (e.g., pip install openpyxl).")
        
        wb = openpyxl.load_workbook(file_path, data_only=True)
        lines = []
        
        if 'reg_define' in wb.sheetnames:
            if 'base_info' in wb.sheetnames:
                lines.append("# base_info\n")
                ws_base = wb['base_info']
                for row in ws_base.iter_rows(values_only=True):
                    if not any(cell is not None and str(cell).strip() != '' for cell in row):
                        continue
                    row_strs = [str(cell).strip() if cell is not None else "" for cell in row]
                    lines.append("| " + " | ".join(row_strs) + " |\n")
            
            lines.append("# reg_define\n")
            ws_reg = wb['reg_define']
            for row in ws_reg.iter_rows(values_only=True):
                if not any(cell is not None and str(cell).strip() != '' for cell in row):
                    continue
                row_strs = [str(cell).strip() if cell is not None else "" for cell in row]
                lines.append("| " + " | ".join(row_strs) + " |\n")
        else:
            ws = wb.active
            for row in ws.iter_rows(values_only=True):
                if not any(cell is not None and str(cell).strip() != '' for cell in row):
                    continue
                
                row_strs = [str(cell).strip() if cell is not None else "" for cell in row]
                
                if row_strs[0].startswith('#'):
                    lines.append(row_strs[0] + "\n")
                else:
                    lines.append("| " + " | ".join(row_strs) + " |\n")
                
        return lines

    def _parse_markdown(self, file_path: str, base_addr: int, max_bytesize: int = None) -> ModuleModel:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_path.endswith('.xlsx'):
            lines = self._read_excel_to_md(file_path)
            content = "".join(lines)
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

        sections = {}
        current_section = None
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('#'):
                current_section = line.lstrip('#').strip().lower()
                sections[current_section] = []
            elif current_section:
                sections[current_section].append(line)

        module = ModuleModel(
            name=os.path.basename(file_path).split('.')[0],
            base_address=base_addr,
            excel_path=file_path
        )

        # 1. Parse base_info
        if 'base_info' in sections:
            base_rows = self._extract_table_rows(sections['base_info'])
            if base_rows:
                info_dict = {row[0]: row[1] for row in base_rows if len(row) >= 2}
                module.base_info.reg_bitwidth = int(info_dict.get('reg_bitwidth', 32))
                module.base_info.author = str(info_dict.get('author', ''))
                module.base_info.email = str(info_dict.get('email', ''))
                
                if 'system_baseaddr' in info_dict:
                    val = info_dict['system_baseaddr']
                    module.base_info.system_baseaddr = int(val.replace('_', ''), 16) if val.startswith('0x') else int(val.replace('_', ''))
                if 'system_bytesize' in info_dict:
                    val = info_dict['system_bytesize']
                    module.base_info.system_bytesize = int(val.replace('_', ''), 16) if val.startswith('0x') else int(val.replace('_', ''))
                if 'system_prefix' in info_dict:
                    module.base_info.system_prefix = str(info_dict['system_prefix'])

        if module.base_info.system_baseaddr is not None:
            base_addr += module.base_info.system_baseaddr
            module.base_address = base_addr
            
        if module.base_info.system_bytesize is not None:
            if max_bytesize is None:
                max_bytesize = module.base_info.system_bytesize
            else:
                max_bytesize = min(max_bytesize, module.base_info.system_bytesize)

        # 2. Parse reg_define
        if 'reg_define' in sections:
            reg_rows, headers = self._extract_table_rows_with_headers(sections['reg_define'])
            if reg_rows:
                self._process_registers(module, reg_rows, headers, base_addr, max_bytesize)

        return module

    def _extract_table_rows(self, lines: List[str]) -> List[List[str]]:
        rows = []
        headers_found = False
        for line in lines:
            line = line.strip()
            if not line.startswith('|'):
                continue
            parts = [p.strip() for p in line.split('|')][1:-1]
            if all(set(p).issubset({'-', ':', ' '}) for p in parts):
                continue
            if not headers_found:
                headers_found = True
                continue
            rows.append(parts)
        return rows

    def _extract_table_rows_with_headers(self, lines: List[str]) -> (List[List[str]], List[str]):
        rows = []
        headers = []
        for line in lines:
            line = line.strip()
            if not line.startswith('|'):
                continue
            parts = [p.strip() for p in line.split('|')][1:-1]
            if all(set(p).issubset({'-', ':', ' '}) for p in parts):
                continue
            if not headers:
                headers = parts
            else:
                rows.append(parts)
        return rows, headers

    def _process_registers(self, module: ModuleModel, rows: List[List[str]], headers: List[str], base_addr: int, max_bytesize: int = None):
        h_idx = {h: i for i, h in enumerate(headers)}
        
        # Pre-pass to count frequencies of reg_names
        name_freq = {}
        for row in rows:
            if len(row) > h_idx.get('reg_name', -1) and 'reg_name' in h_idx:
                r_name = row[h_idx['reg_name']].strip()
                if r_name:
                    name_freq[r_name] = name_freq.get(r_name, 0) + 1

        last_reg_name = ""
        last_reg_type = ""
        last_special = ""
        
        reg_counts = {}
        def deduplicate_name(name):
            if not name: return name
            if name_freq.get(name, 0) > 1:
                reg_counts[name] = reg_counts.get(name, 0) + 1
                return f"{name}{reg_counts[name]}"
            return name

        registers_data = []
        current_reg = None
        
        last_offset = -1
        expected_next_offset = 0
        valid_types = ['cfg', 'status', 'cmd', 'irq', 'slave', 'mem']

        max_addr_used = 0

        for row in rows:
            while len(row) < len(headers):
                row.append('')
            
            offset_raw = row[h_idx['offset']] if 'offset' in h_idx else ''
            reg_name_raw = row[h_idx['reg_name']] if 'reg_name' in h_idx else ''
            
            is_new_reg = bool(offset_raw) or bool(reg_name_raw)
            
            if is_new_reg:
                if reg_name_raw: last_reg_name = reg_name_raw
                
                type_raw = row[h_idx['reg_type']] if 'reg_type' in h_idx else ''
                if type_raw: last_reg_type = type_raw
                
                special_raw = row[h_idx['special']] if 'special' in h_idx else ''
                if special_raw: last_special = special_raw
                
                # Calculate offset and enforce Rule 7
                if offset_raw:
                    offset_val = int(offset_raw, 16) if '0x' in offset_raw.lower() else int(offset_raw)
                    if last_offset >= 0 and offset_val <= last_offset:
                        prev_reg = registers_data[-1] if registers_data else None
                        error_msg = f"Address Error in {module.name}:\n  Offset {hex(offset_val)} is not strictly increasing.\n"
                        if prev_reg:
                            error_msg += (
                                f"  Previous register info:\n"
                                f"    reg_name: {prev_reg['raw_name']}\n"
                                f"    offset: {hex(prev_reg['offset'] - base_addr)}\n"
                                f"    reg_type: {prev_reg['reg_type']}\n"
                                f"    special: {prev_reg['special']}\n"
                            )
                        error_msg += (
                            f"  Current register info:\n"
                            f"    reg_name: {reg_name_raw}\n"
                            f"    offset: {hex(offset_val)}\n"
                            f"    reg_type: {type_raw}\n"
                            f"    special: {special_raw}\n"
                        )
                        raise ValueError(error_msg)
                    if expected_next_offset > 0 and offset_val < expected_next_offset:
                        prev_reg = registers_data[-1]
                        error_msg = (
                            f"Address Overlap Error in {module.name}:\n"
                            f"  Current register '{reg_name_raw}' at offset {hex(offset_val)} overlaps with previous register.\n"
                            f"  Previous register info:\n"
                            f"    reg_name: {prev_reg['raw_name']}\n"
                            f"    offset: {hex(prev_reg['offset'] - base_addr)}\n"
                            f"    reg_type: {prev_reg['reg_type']}\n"
                            f"    special: {prev_reg['special']}\n"
                            f"    expected next available offset: {hex(expected_next_offset)}\n"
                            f"  Current register info:\n"
                            f"    reg_name: {reg_name_raw}\n"
                            f"    offset: {hex(offset_val)}\n"
                            f"    reg_type: {type_raw}\n"
                            f"    special: {special_raw}\n"
                        )
                        raise ValueError(error_msg)
                else:
                    offset_val = expected_next_offset
                
                last_offset = offset_val
                
                # Calculate expected next offset based on repeat or bytesize
                repeat_count = 1
                bytesize = None
                for part in last_special.split(','):
                    part = part.strip()
                    if part.startswith('repeat'):
                        try:
                            repeat_count = int(part.split()[1])
                        except ValueError:
                            pass
                    elif part.startswith('bytesize='):
                        try:
                            bytesize_str = part.split('=')[1].strip()
                            bytesize = int(bytesize_str, 16) if '0x' in bytesize_str.lower() else int(bytesize_str)
                        except ValueError:
                            pass
                
                if last_reg_type in ['slave', 'mem'] and bytesize is not None:
                    expected_next_offset = offset_val + bytesize
                else:
                    expected_next_offset = offset_val + (repeat_count * (module.base_info.reg_bitwidth // 8))
                
                if expected_next_offset > max_addr_used:
                    max_addr_used = expected_next_offset
                
                unique_name = deduplicate_name(last_reg_name)
                
                reg_type = last_reg_type.lower()
                if reg_type not in valid_types:
                    print(f"[Warning] Invalid reg_type: {reg_type} at offset {hex(offset_val)}. Expected one of {valid_types}")

                current_reg = {
                    'name': unique_name,
                    'raw_name': last_reg_name,
                    'offset': base_addr + offset_val,
                    'reg_type': reg_type,
                    'special': last_special,
                    'fields': []
                }
                registers_data.append(current_reg)

            # Add field
            field_name = row[h_idx['field']] if 'field' in h_idx else ''
            if field_name:
                msb_raw = row[h_idx['msb']] if 'msb' in h_idx else '0'
                lsb_raw = row[h_idx['lsb']] if 'lsb' in h_idx else '0'
                sw_access = row[h_idx['SW_access']] if 'SW_access' in h_idx else ''
                default_val = row[h_idx['default_value']] if 'default_value' in h_idx else ''
                desc = row[h_idx['description']] if 'description' in h_idx else ''
                
                field = FieldModel(
                    name=field_name,
                    msb=int(msb_raw) if msb_raw.isdigit() else 0,
                    lsb=int(lsb_raw) if lsb_raw.isdigit() else 0,
                    sw_access=sw_access,
                    default_value=default_val,
                    description=desc
                )
                if current_reg:
                    current_reg['fields'].append(field)

        if max_bytesize is not None and max_addr_used > max_bytesize:
            last_reg = registers_data[-1] if registers_data else None
            error_msg = (
                f"Address Space Exceeded Error in {module.name}:\n"
                f"  Total address space used ({hex(max_addr_used)}) exceeds allocated bytesize ({hex(max_bytesize)}).\n"
            )
            if last_reg:
                error_msg += (
                    f"  Last register info:\n"
                    f"    reg_name: {last_reg['raw_name']}\n"
                    f"    offset: {hex(last_reg['offset'] - base_addr)}\n"
                    f"    reg_type: {last_reg['reg_type']}\n"
                    f"    special: {last_reg['special']}\n"
                )
            raise ValueError(error_msg)

        # Infer missing bytesize for slave/mem
        for i, reg_data in enumerate(registers_data):
            if reg_data['reg_type'] in ['slave', 'mem']:
                has_bytesize = False
                for part in reg_data['special'].split(','):
                    if part.strip().startswith('bytesize='):
                        has_bytesize = True
                        break
                
                if not has_bytesize:
                    if i + 1 < len(registers_data):
                        next_offset = registers_data[i+1]['offset'] - base_addr
                        inferred_bytesize = next_offset - (reg_data['offset'] - base_addr)
                    else:
                        if max_bytesize is not None:
                            inferred_bytesize = max_bytesize - (reg_data['offset'] - base_addr)
                        else:
                            inferred_bytesize = None
                    
                    if inferred_bytesize is not None:
                        if reg_data['special'] and reg_data['special'] != '-':
                            reg_data['special'] += f", bytesize=0x{inferred_bytesize:X}"
                        else:
                            reg_data['special'] = f"bytesize=0x{inferred_bytesize:X}"

        for reg_data in registers_data:
            reg = RegisterModel(
                name=reg_data['name'],
                offset=reg_data['offset'],
                reg_type=reg_data['reg_type'],
                special=reg_data['special'],
                description=""
            )
            reg.fields = reg_data['fields']
            module.registers.append(reg)

            if reg.reg_type == 'slave':
                special_parts = [p.strip() for p in reg.special.split(',')]
                slv_filename = ""
                for part in special_parts:
                    if part.startswith('slv_filename='):
                        slv_filename = part.split('=')[1].strip()
                        break
                
                if not slv_filename:
                    raise ValueError(f"Error in {module.name}: reg_type='slave' but no 'slv_filename' specified in special column for register '{reg.name}'.")
                
                sub_path = os.path.join(os.path.dirname(module.excel_path), slv_filename)
                if not os.path.exists(sub_path):
                    raise FileNotFoundError(f"Error in {module.name}: slv_filename '{slv_filename}' not found at {sub_path} for register '{reg.name}'.")

                if self.nested:
                    self._handle_slave(module, reg)

    def _handle_slave(self, module: ModuleModel, reg: RegisterModel):
        special_parts = [p.strip() for p in reg.special.split(',')]
        slv_filename = ""
        bytesize = None
        
        for part in special_parts:
            if part.startswith('slv_filename='):
                slv_filename = part.split('=')[1].strip()
            elif part.startswith('bytesize='):
                try:
                    bytesize_str = part.split('=')[1].strip()
                    bytesize = int(bytesize_str, 16) if '0x' in bytesize_str.lower() else int(bytesize_str)
                except ValueError:
                    pass
        
        if slv_filename:
            sub_path = os.path.join(os.path.dirname(module.excel_path), slv_filename)
            if os.path.exists(sub_path):
                module.is_leaf = False
                sub_inst = SubModuleInstance(
                    instance_name=reg.name,
                    module_name=os.path.basename(slv_filename).split('.')[0],
                    offset=reg.offset,
                    excel_path=sub_path,
                    bytesize=bytesize
                )
                # Pass bytesize down to enforce Rule 8
                sub_inst.module_obj = self.parse(sub_path, base_addr=sub_inst.offset, max_bytesize=bytesize)
                module.sub_modules.append(sub_inst)
