#!/usr/bin/env python3
import json
import re
from pathlib import Path

# 正则捕获：1.GLOBAL 2.方向 3.类型 4.位宽 5.信号名 6.名后空格 7.逗号
REGEX_SIGNAL = re.compile(r'^\s*(GLOBAL:)?\s*(input|output)\s+(\w+)\s+(?:\[(.*?)\])?\s*(\w+)(\s*)(,)?')

def get_project_root():
    """定位项目根目录"""
    return Path(__file__).resolve().parent.parent

def calc_width(width_raw, params):
    """处理位宽计算或透传"""
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
    """解析模板及角色定义"""
    path = get_project_root() / "cfg" / tpl_filename
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")

    content = path.read_text(encoding='utf-8')
    sections = {}
    current_label = None

    for line in content.splitlines():
        line_strip = line.strip()
        if line_strip.startswith('[') and line_strip.endswith(']'):
            raw_tag = line_strip[1:-1]
            label, role = raw_tag.split(':') if ':' in raw_tag else (raw_tag, None)
            current_label = label
            sections[current_label] = {"role": role, "lines": []}
        elif current_label and line_strip and not line_strip.startswith('//'):
            sections[current_label]["lines"].append(line)
    return sections

def generate_rtl(cfg_name):
    """核心逻辑：对每个 prefix 依次生成 Master 和 Slave 信号"""
    cfg_path = get_project_root() / cfg_name
    config = json.loads(cfg_path.read_text(encoding='utf-8'))
    tpl_filename = config.get("template_file", "template.txt")
    templates = load_template(tpl_filename)

    raw_port_data = []
    seen_globals = set()

    for inst in config['instances']:
        prefixes = inst['prefix']
        if isinstance(prefixes, str):
            prefixes = [prefixes]

        label = inst['protocol']
        base_mode = inst.get('mode', 'master')
        params = inst.get('params', {})

        if label not in templates:
            continue
        tpl_info = templates[label]

        # 遍历每一个 prefix
        for pfx in prefixes:
            pfx = pfx.lower()

            # 根据交替模式确定需要生成的模式列表
            # m_s_alt: 对该 prefix 先生成 Master 再生成 Slave
            # s_m_alt: 对该 prefix 先生成 Slave 再生成 Master
            if base_mode == 'm_s_alt':
                modes_to_gen = ['master', 'slave']
            elif base_mode == 's_m_alt':
                modes_to_gen = ['slave', 'master']
            else:
                modes_to_gen = [base_mode]

            # 在 prefix 内部循环生成指定的模式
            for curr_mode in modes_to_gen:
                raw_port_data.append({"type": "comment", "content": f"// --- {pfx} ({label.upper()} {curr_mode.upper()}) ---"})

                for line in tpl_info["lines"]:
                    match = REGEX_SIGNAL.search(line)
                    if not match: continue

                    is_global, raw_dir, raw_type, raw_width, suffix, spaces, _ = match.groups()

                    # GLOBAL 信号仅生成一次
                    if is_global:
                        sig_key = f"{label}_{suffix.lower()}"
                        if sig_key not in seen_globals:
                            raw_port_data.append({
                                "type": "port", "dir": raw_dir, "decl": raw_type,
                                "width": calc_width(raw_width, params),
                                "name": suffix.lower(),
                                "space_len": len(spaces)
                            })
                            seen_globals.add(sig_key)
                        continue

                    # 方向判定：角色不匹配则翻转
                    if tpl_info["role"] and tpl_info["role"] != curr_mode[0].upper():
                        final_dir = 'output' if raw_dir == 'input' else 'input'
                    else:
                        final_dir = ('output' if raw_dir == 'input' else 'input') if (curr_mode == 'slave' and not tpl_info["role"]) else raw_dir

                    raw_port_data.append({
                        "type": "port", "dir": final_dir, "decl": raw_type,
                        "width": calc_width(raw_width, params),
                        "name": f"{pfx}_{suffix.lower().lstrip('_')}",
                        "space_len": len(spaces)
                    })

    # 动态对齐逻辑
    max_w_len = max([len(i["width"]) for i in raw_port_data if i["type"] == "port"] or [0])
    max_d_len = max([len(i["decl"]) for i in raw_port_data if i["type"] == "port"] or [0])
    max_n_len = max([len(i["name"]) for i in raw_port_data if i["type"] == "port"] or [0])

    ports_idx = [idx for idx, x in enumerate(raw_port_data) if x["type"] == "port"]
    last_idx = ports_idx[-1] if ports_idx else -1

    formatted = []
    for i, item in enumerate(raw_port_data):
        if item["type"] == "comment":
            formatted.append(f"    {item['content']}")
        else:
            comma = "" if i == last_idx else ","
            w_str = f" {item['width']}" if item['width'] else ""
            line = f"    {item['dir']:<6} {item['decl']:<{max_d_len}} {w_str:<{max_w_len+1}}{item['name']:<{max_n_len}}{' '*item['space_len']}{comma}"
            formatted.append(line)

    return f"module {config['module_name']} (\n" + "\n".join(formatted) + "\n);\n\nendmodule"

if __name__ == "__main__":
    try:
        verilog_content = generate_rtl('config.json')
        output_dir = get_project_root() / "out"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "amba_top.sv"
        output_file.write_text(verilog_content, encoding='utf-8')
        print(f"Successfully generated SV: {output_file}")
    except Exception as e:
        print(f"Error: {e}")