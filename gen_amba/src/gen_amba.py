#!/usr/bin/env python3
import json
import re
import argparse
from pathlib import Path

# 正则捕获：1.GLOBAL 2.方向 3.类型 4.位宽 5.信号名 6.名后空格 7.逗号
REGEX_SIGNAL = re.compile(r'^\s*(GLOBAL:)?\s*(input|output)\s+(\w+)\s+(?:\[(.*?)\])?\s*(\w+)(\s*)(,)?')

def get_project_root():
    return Path(__file__).resolve().parent.parent

def calc_width(width_raw, params):
    if not width_raw: return ""
    expr = width_raw
    for k, v in params.items():
        if k in expr: expr = expr.replace(k, str(v))
    parts = expr.split(':')
    res = []
    for p in parts:
        try: res.append(str(int(eval(p))))
        except: res.append(p)
    return f"[{':'.join(res)}]"

def get_dynamic_prefix(pfx, is_flipped):
    if "__" in pfx and is_flipped:
        parts = pfx.split("__")
        return "__".join(reversed(parts))
    return pfx

def load_template(tpl_filename):
    path = get_project_root() / "cfg" / tpl_filename
    if not path.exists(): raise FileNotFoundError(f"Template not found: {path}")
    content = path.read_text(encoding='utf-8')
    sections = {}
    current_label = None
    for line in content.splitlines():
        line_strip = line.strip()
        if line_strip.startswith('[') and line_strip.endswith(']'):
            raw_tag = line_strip[1:-1]
            label, role = raw_tag.split(':') if ':' in raw_tag else (raw_tag, None)
            current_label = label
            sections[current_label] = {"role_tag": role, "lines": []}
        elif current_label and line_strip and not line_strip.startswith('//'):
            sections[current_label]["lines"].append(line)
    return sections

def generate_rtl(cfg_name):
    # 如果 cfg_name 是绝对路径则直接使用，否则相对于项目根目录寻找
    cfg_path = Path(cfg_name) if Path(cfg_name).is_absolute() else get_project_root() / cfg_name
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")

    config = json.loads(cfg_path.read_text(encoding='utf-8'))
    tpl_filename = config.get("template_file", "template.txt")
    templates = load_template(tpl_filename)

    raw_port_data = []
    seen_globals = set()

    for inst in config['instances']:
        prefixes = inst['prefix']
        if isinstance(prefixes, str): prefixes = [prefixes]
        label = inst['protocol']
        base_mode = inst.get('mode', 'master')
        params = inst.get('params', {})
        if label not in templates: continue
        tpl_info = templates[label]

        for pfx in prefixes:
            if base_mode == 'm_s_alt':
                modes_to_gen = [('master', False), ('slave', True)]
            elif base_mode == 's_m_alt':
                modes_to_gen = [('slave', False), ('master', True)]
            else:
                modes_to_gen = [(base_mode, False)]

            for curr_mode, is_flipped in modes_to_gen:
                active_pfx = get_dynamic_prefix(pfx, is_flipped).lower()
                raw_port_data.append({"type": "comment", "content": f"// --- {active_pfx} ({label.upper()} {curr_mode.upper()}) ---"})

                for line in tpl_info["lines"]:
                    match = REGEX_SIGNAL.search(line)
                    if not match: continue
                    is_global, raw_dir, raw_type, raw_width, suffix, spaces, _ = match.groups()

                    if is_global:
                        if f"{label}_{suffix.lower()}" not in seen_globals:
                            raw_port_data.append({
                                "type": "port", "dir": raw_dir, "decl": raw_type,
                                "width": calc_width(raw_width, params), "name": suffix.lower(),
                                "tpl_space_len": len(spaces)
                            })
                            seen_globals.add(f"{label}_{suffix.lower()}")
                        continue

                    role_defined = tpl_info["role_tag"]
                    if role_defined and role_defined != curr_mode[0].upper():
                        final_dir = 'output' if raw_dir == 'input' else 'input'
                    else:
                        final_dir = ('output' if raw_dir == 'input' else 'input') if (curr_mode == 'slave' and not role_defined) else raw_dir

                    raw_port_data.append({
                        "type": "port", "dir": final_dir, "decl": raw_type,
                        "width": calc_width(raw_width, params),
                        "name": f"{active_pfx}_{suffix.lower().lstrip('_')}",
                        "tpl_space_len": len(spaces)
                    })

    # --- 像素级对齐逻辑 ---
    max_d_len = max([len(i["decl"]) for i in raw_port_data if i["type"] == "port"] or [0])
    max_w_len = max([len(i["width"]) for i in raw_port_data if i["type"] == "port"] or [0])

    # 核心：计算全局最大列基准，确保逗号绝对垂直对齐
    max_name_end_col = max([(len(i["name"]) + i["tpl_space_len"]) for i in raw_port_data if i["type"] == "port"] or [0])

    ports_idx = [idx for idx, x in enumerate(raw_port_data) if x["type"] == "port"]
    last_idx = ports_idx[-1] if ports_idx else -1

    formatted = []
    for i, item in enumerate(raw_port_data):
        if item["type"] == "comment":
            formatted.append(f"    {item['content']}")
        else:
            comma = "" if i == last_idx else ","
            # 前部对齐 (wire [] 间距收紧)
            w_field = f" {item['width']}" if item['width'] else ""
            line_prefix = f"    {item['dir']:<6} {item['decl']:<{max_d_len}}{w_field:<{max_w_len+1}}"

            # 中缝：10个空格
            middle_gap = " " * 10

            # 尾部对齐：确保逗号垂直
            padding_len = max_name_end_col - len(item["name"])
            name_and_padding = f"{item['name']}{' ' * padding_len}"

            formatted.append(f"{line_prefix}{middle_gap}{name_and_padding}{comma}")

    return f"module {config['module_name']} (\n" + "\n".join(formatted) + "\n);\n\nendmodule"

if __name__ == "__main__":
    # 命令行参数配置
    parser = argparse.ArgumentParser(description='AMBA RTL Generator')
    parser.add_argument('config_file', nargs='?', default='config.json',
                        help='Path to the config file (default: config.json)')
    args = parser.parse_args()

    try:
        verilog_content = generate_rtl(args.config_file)
        output_file = get_project_root() / "out" / "amba_top.sv"
        output_file.parent.mkdir(exist_ok=True)
        output_file.write_text(verilog_content, encoding='utf-8')
        print(f"Successfully generated RTL from '{args.config_file}' -> {output_file}")
    except Exception as e:
        print(f"Error: {e}")