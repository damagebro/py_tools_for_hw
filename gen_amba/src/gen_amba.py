#!/usr/bin/env python3
import json
import re
from pathlib import Path

# 增强型正则：捕获 1.GLOBAL 2.方向 3.类型 4.位宽 5.信号名 6.名后空格 7.结尾逗号
REGEX_SIGNAL = re.compile(
    r'^\s*(GLOBAL:)?\s*(input|output)\s+(\w+)\s+(?:\[(.*?)\])?\s*(\w+)(\s*)(,)?'
)

def get_project_root():
    return Path(__file__).resolve().parent.parent

def calc_width(width_raw, params):
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
        raise FileNotFoundError(f"Template not found: {path}")
    content = path.read_text(encoding='utf-8')
    sections = {}
    current_sec = None
    for line in content.splitlines():
        line_strip = line.strip()
        if line_strip.startswith('[') and line_strip.endswith(']'):
            current_sec = line_strip[1:-1]
            sections[current_sec] = []
        elif current_sec and line_strip and not line_strip.startswith('//'):
            sections[current_sec].append(line) # 保留原始行用于提取空格
    return sections

def generate_rtl(cfg_name):
    cfg_path = get_project_root() / cfg_name
    config = json.loads(cfg_path.read_text(encoding='utf-8'))
    tpl_filename = config.get("template_file", "template.txt")
    templates = load_template(tpl_filename)

    raw_port_data = []
    seen_globals = set()

    for inst in config['instances']:
        prefixes = inst['prefix']
        if isinstance(prefixes, str): prefixes = [prefixes]
        protocol = inst['protocol']
        mode = inst.get('mode', 'master')
        params = inst.get('params', {})

        if protocol not in templates: continue

        for pfx in prefixes:
            pfx = pfx.lower()
            raw_port_data.append({"type": "comment", "content": f"// --- Interface: {pfx} ({protocol.upper()} {mode.upper()}) ---"})

            for line in templates[protocol]:
                match = REGEX_SIGNAL.search(line)
                if not match: continue
                is_global, raw_dir, raw_type, raw_width, suffix, trailing_spaces, has_comma = match.groups()

                # 计算信号名后的原始空格长度
                space_len = len(trailing_spaces) if trailing_spaces else 0

                if is_global:
                    sig_key = f"{protocol}_{suffix.lower()}"
                    if sig_key not in seen_globals:
                        raw_port_data.append({
                            "type": "port", "dir": raw_dir, "decl": raw_type,
                            "width": calc_width(raw_width, params), "name": suffix.lower(),
                            "space_len": space_len, "is_global": True
                        })
                        seen_globals.add(sig_key)
                    continue

                final_dir = 'output' if (mode == 'slave' and raw_dir == 'input') or (mode == 'master' and raw_dir == 'output') else 'input'
                raw_port_data.append({
                    "type": "port", "dir": final_dir, "decl": raw_type,
                    "width": calc_width(raw_width, params),
                    "name": f"{pfx}_{suffix.lower().lstrip('_')}",
                    "space_len": space_len, "is_global": False
                })

    # --- 对齐逻辑 ---
    max_w_len = max([len(i["width"]) for i in raw_port_data if i["type"] == "port"] or [0])
    max_d_len = max([len(i["decl"]) for i in raw_port_data if i["type"] == "port"] or [0])

    # 注意：不再统一对齐信号名后的逗号，而是根据 space_len 决定位置
    formatted_lines = []
    ports_indices = [i for i, x in enumerate(raw_port_data) if x["type"] == "port"]
    last_port_idx = ports_indices[-1] if ports_indices else -1

    for i, item in enumerate(raw_port_data):
        if item["type"] == "comment":
            formatted_lines.append(f"    {item['content']}")
        else:
            is_last = (i == last_port_idx)
            comma = "" if is_last else ","
            # 如果后台模板里信号名后没空格且有逗号，或者指定了特定空格，则按后台来
            # 我们用 space_len 来填充信号名与逗号之间的距离
            spaces = " " * item["space_len"]
            w_str = f" {item['width']}" if item['width'] else ""

            line = f"    {item['dir']:<6} {item['decl']:<{max_d_len}} {w_str:<{max_w_len+1}}{item['name']}{spaces}{comma}"
            formatted_lines.append(line)

    return f"module {config['module_name']} (\n" + "\n".join(formatted_lines) + "\n);\n\nendmodule"

if __name__ == "__main__":
    try:
        verilog = generate_rtl('config.json')
        out_dir = get_project_root() / "out"
        out_dir.mkdir(exist_ok=True)
        (out_dir / "amba_top.sv").write_text(verilog, encoding='utf-8')
        print(f"Generated: out/amba_top.sv")
    except Exception as e:
        print(f"Error: {e}")