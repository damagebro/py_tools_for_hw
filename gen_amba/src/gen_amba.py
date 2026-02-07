#!/usr/bin/env python3
import json
import re
from pathlib import Path

# 正则：支持 GLOBAL 标记、位宽和信号名抓取
REGEX_SIGNAL = re.compile(r'^\s*(GLOBAL:)?\s*(input|output)\s+(?:wire\s+)?(?:\[(.*?)\])?\s*(\w+)')

def get_project_root():
    """获取项目根目录"""
    return Path(__file__).resolve().parent.parent

def calc_width(width_raw, params):
    """参数替换与计算：前台有则转数值，无则保留"""
    if not width_raw: return ""
    expr = width_raw
    for k, v in params.items():
        if k in expr:
            expr = expr.replace(k, str(v))

    parts = expr.split(':')
    res = []
    for p in parts:
        try:
            val = int(eval(p))
            res.append(str(val))
        except:
            res.append(p)
    return f"[{':'.join(res)}]"

def load_template(filename):
    """直接使用 pathlib 读取模板文件"""
    path = get_project_root() / "cfg" / filename
    if not path.exists(): return {}

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

def generate_rtl(tpl_name, cfg_name):
    templates = load_template(tpl_name)
    cfg_path = get_project_root() / cfg_name

    # 直接读取并解析 JSON
    config = json.loads(cfg_path.read_text(encoding='utf-8'))

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

            is_global, raw_dir, raw_width, suffix = match.groups()
            suffix = suffix.lower()

            if is_global:
                sig_key = f"{protocol}_{suffix}"
                if sig_key not in seen_globals:
                    raw_port_data.append({
                        "type": "port",
                        "dir": raw_dir,
                        "width": calc_width(raw_width, params),
                        "name": suffix
                    })
                    seen_globals.add(sig_key)
                continue

            final_dir = 'output' if (mode == 'slave' and raw_dir == 'input') or (mode == 'master' and raw_dir == 'output') else 'input'
            raw_port_data.append({
                "type": "port",
                "dir": final_dir,
                "width": calc_width(raw_width, params),
                "name": f"{prefix}_{suffix.lstrip('_')}"
            })

    # --- 对齐逻辑 ---
    max_w_len = 0
    for item in raw_port_data:
        if item["type"] == "port":
            max_w_len = max(max_w_len, len(item["width"]))

    formatted_lines = []
    ports_only = [i for i, x in enumerate(raw_port_data) if x["type"] == "port"]
    last_port_idx = ports_only[-1] if ports_only else -1

    for i, item in enumerate(raw_port_data):
        if item["type"] == "comment":
            formatted_lines.append(f"    {item['content']}")
        else:
            comma = "," if i < last_port_idx else ""
            w_str = f" {item['width']}" if item['width'] else ""
            line = f"    {item['dir']:<6} wire {w_str:<{max_w_len+1}}{item['name']}{comma}"
            formatted_lines.append(line)

    return f"module {config['module_name']} (\n" + "\n".join(formatted_lines) + "\n);\n\nendmodule"

if __name__ == "__main__":
    try:
        verilog = generate_rtl('template.txt', 'config.json')
        output_path = get_project_root() / "amba_top.v"
        # 直接写入文本
        output_path.write_text(verilog, encoding='utf-8')
        print(f"Generated successfully: {output_path}")
    except Exception as e:
        print(f"Error: {e}")