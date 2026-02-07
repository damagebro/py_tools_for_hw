#!/usr/bin/env python3
import json
import re
from pathlib import Path

# 正则：匹配信号行，支持 GLOBAL、方向、类型、位宽和信号名
REGEX_SIGNAL = re.compile(r'^\s*(GLOBAL:)?\s*(input|output)\s+(\w+)\s+(?:\[(.*?)\])?\s*(\w+)')

def get_project_root():
    """获取项目根目录"""
    return Path(__file__).resolve().parent.parent

def calc_width(width_raw, params):
    """参数计算规则：匹配则转数值，不匹配则透传"""
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
    """根据前台指定的文件名读取模板"""
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
    # 1. 先读前台配置
    cfg_path = get_project_root() / cfg_name
    config = json.loads(cfg_path.read_text(encoding='utf-8'))

    # 2. 获取模板文件名，默认为 template.txt
    tpl_filename = config.get("template_file", "template.txt")
    templates = load_template(tpl_filename)

    raw_port_data = []
    seen_globals = set()

    for inst in config['instances']:
        prefix = inst['prefix'].lower()
        protocol = inst['protocol']
        mode = inst.get('mode', 'master')
        params = inst.get('params', {})
        if protocol not in templates: continue

        raw_port_data.append({"type": "comment", "content": f"// --- Interface: {prefix} ({protocol.upper()} {mode.upper()}) ---"})
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

            # 自动翻转 Master/Slave 方向
            final_dir = 'output' if (mode == 'slave' and raw_dir == 'input') or (mode == 'master' and raw_dir == 'output') else 'input'
            raw_port_data.append({
                "type": "port", "dir": final_dir, "decl": raw_type,
                "width": calc_width(raw_width, params),
                "name": f"{prefix}_{suffix.lstrip('_')}"
            })

    # 动态对齐逻辑
    max_w_len = max([len(i["width"]) for i in raw_port_data if i["type"] == "port"] or [0])
    max_d_len = max([len(i["decl"]) for i in raw_port_data if i["type"] == "port"] or [0])

    formatted_lines = []
    ports_only = [i for i, x in enumerate(raw_port_data) if x["type"] == "port"]
    last_port_idx = ports_only[-1] if ports_only else -1

    for i, item in enumerate(raw_port_data):
        if item["type"] == "comment":
            formatted_lines.append(f"    {item['content']}")
        else:
            comma = "," if i < last_port_idx else ""
            w_str = f" {item['width']}" if item['width'] else ""
            line = f"    {item['dir']:<6} {item['decl']:<{max_d_len}} {w_str:<{max_w_len+1}}{item['name']}{comma}"
            formatted_lines.append(line)

    return f"module {config['module_name']} (\n" + "\n".join(formatted_lines) + "\n);\n\nendmodule"

if __name__ == "__main__":
    try:
        verilog = generate_rtl('config.json')
        out_dir = get_project_root() / "out"
        out_dir.mkdir(exist_ok=True)
        output_path = out_dir / "amba_top.sv"
        output_path.write_text(verilog, encoding='utf-8')
        print(f"Generated successfully in: {output_path}")
    except Exception as e:
        print(f"Error: {e}")