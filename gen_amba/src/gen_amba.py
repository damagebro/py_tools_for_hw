#!/usr/bin/env python3
import json
import re
from pathlib import Path

# 正则：匹配信号行
REGEX_SIGNAL = re.compile(r'^\s*(GLOBAL:)?\s*(input|output)\s+(\w+)\s+(?:\[(.*?)\])?\s*(\w+)')

def get_project_root():
    return Path(__file__).resolve().parent.parent

def calc_width(width_raw, params):
    """参数计算与透传逻辑"""
    if not width_raw: return ""
    expr = width_raw
    for k, v in params.items():
        if k in expr:
            expr = expr.replace(k, str(v))
    parts = expr.split(':')
    res = []
    for p in parts:
        try:
            res.append(str(int(eval(p))))
        except:
            res.append(p)
    return f"[{':'.join(res)}]"

def load_template(tpl_filename):
    path = get_project_root() / "cfg" / tpl_filename
    if not path.exists():
        raise FileNotFoundError(f"Template file not found: {path}")
    content = path.read_text(encoding='utf-8')
    sections = {}
    current_sec = None
    for line in content.splitlines():
        line = line.strip()
        if line.startswith('[') and line.endswith(']'):
            current_sec = line[1:-1]
            sections[current_sec] = []
        elif current_sec and line and not line.startswith('//'):
            sections[current_sec].append(line)
    return sections

def generate_rtl(cfg_name):
    cfg_path = get_project_root() / cfg_name
    config = json.loads(cfg_path.read_text(encoding='utf-8'))
    tpl_filename = config.get("template_file", "template.txt")
    templates = load_template(tpl_filename)

    raw_port_data = []
    seen_globals = set()

    for inst in config['instances']:
        # 升级：支持 prefix 是字符串或列表
        prefixes = inst['prefix']
        if isinstance(prefixes, str):
            prefixes = [prefixes]

        protocol = inst['protocol']
        mode = inst.get('mode', 'master')
        params = inst.get('params', {})
        if protocol not in templates: continue

        # 按前缀顺序输出每组信号
        for pfx in prefixes:
            pfx = pfx.lower()
            raw_port_data.append({"type": "comment", "content": f"// --- Interface: {pfx} ({protocol.upper()} {mode.upper()}) ---"})

            for line in templates[protocol]:
                match = REGEX_SIGNAL.search(line)
                if not match: continue
                is_global, raw_dir, raw_type, raw_width, suffix = match.groups()
                suffix = suffix.lower()

                if is_global:
                    sig_key = f"{protocol}_{suffix}"
                    if sig_key not in seen_globals:
                        raw_port_data.append({
                            "type": "port", "dir": raw_dir, "decl": raw_type,
                            "width": calc_width(raw_width, params), "name": suffix
                        })
                        seen_globals.add(sig_key)
                    continue

                final_dir = 'output' if (mode == 'slave' and raw_dir == 'input') or (mode == 'master' and raw_dir == 'output') else 'input'
                raw_port_data.append({
                    "type": "port", "dir": final_dir, "decl": raw_type,
                    "width": calc_width(raw_width, params),
                    "name": f"{pfx}_{suffix.lstrip('_')}"
                })

    # --- 对齐逻辑升级：增加对信号名长度的统计以对齐逗号 ---
    max_w_len = max([len(i["width"]) for i in raw_port_data if i["type"] == "port"] or [0])
    max_d_len = max([len(i["decl"]) for i in raw_port_data if i["type"] == "port"] or [0])
    max_n_len = max([len(i["name"]) for i in raw_port_data if i["type"] == "port"] or [0])

    formatted_lines = []
    ports_only_indices = [i for i, x in enumerate(raw_port_data) if x["type"] == "port"]
    last_port_idx = ports_only_indices[-1] if ports_only_indices else -1

    for i, item in enumerate(raw_port_data):
        if item["type"] == "comment":
            formatted_lines.append(f"    {item['content']}")
        else:
            comma = "," if i < last_port_idx else ""
            w_str = f" {item['width']}" if item['width'] else ""
            # 方向(6) + 类型(max_d) + 位宽(max_w+1) + 信号名(max_n) + 逗号
            line = f"    {item['dir']:<6} {item['decl']:<{max_d_len}} {w_str:<{max_w_len+1}}{item['name']:<{max_n_len}}{comma}"
            formatted_lines.append(line)

    return f"module {config['module_name']} (\n" + "\n".join(formatted_lines) + "\n);\n\nendmodule"

if __name__ == "__main__":
    try:
        verilog = generate_rtl('config.json')
        out_dir = get_project_root() / "out"
        out_dir.mkdir(exist_ok=True)
        (out_dir / "amba_top.sv").write_text(verilog, encoding='utf-8')
        print(f"Generated successfully in: out/amba_top.sv")
    except Exception as e:
        print(f"Error: {e}")