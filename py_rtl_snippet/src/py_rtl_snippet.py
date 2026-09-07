#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path


SNIPPET_MD_PATH = Path(__file__).resolve().parents[1] / "input" / "rtl_snippets.md"
SNIPPET_JSON_PATH = (
    Path(__file__).resolve().parents[1]
    / "snippets"
    / "systemverilog.code-snippets"
)
DEFAULT_COMMON_ROOT = Path(__file__).resolve().parents[3] / "com"
DEFAULT_RTL_INST_SCRIPT = (
    Path(__file__).resolve().parents[2] / "gen_rtl_inst" / "src" / "gen_rtl_inst.py"
)
ALWAYS_PREFIXES = (
    "rtl-always_dff_no_rst",
    "rtl-always_dff",
    "rtl-always_dff_begin_end",
    "rtl-always_comb",
)
PORT_PREFIXES = (
    "rtl-vld_rdy",
    "rtl-ram_port",
    "rtl-csr_port",
    "rtl-ebus_rdport",
    "rtl-ebus_wrport",
    "rtl-apb_port",
    "rtl-axi4_port",
)
DEFAULT_PLACEHOLDER_RE = re.compile(r"\$\{(\d+):([^{}]*)\}")
REFERENCE_PLACEHOLDER_RE = re.compile(r"\$\{(\d+)\}|\$(\d+)")
SECTION_RE = re.compile(r"(?ms)^##\s+(?P<prefix>\S+)\s*\n(?P<content>.*?)(?=^##\s+|\Z)")
META_RE = re.compile(r"(?m)^-\s*(?P<key>title|description|scope)\s*:\s*(?P<value>.+?)\s*$")
CODE_BLOCK_RE = re.compile(r"(?ms)^```(?:systemverilog|verilog|sv)\s*\n(?P<body>.*?)^```\s*$")
RTL_INST_PREFIX = "rtl-inst"
TABLE_SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")


def parse_table(section: str) -> list[dict[str, str]]:
    rows = []
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and all(TABLE_SEPARATOR_RE.fullmatch(cell) for cell in cells):
            continue
        rows.append([cell.strip("`") for cell in cells])
    if not rows:
        return []
    header = rows[0]
    required = {"module_name", "rtl_path", "description"}
    if not required <= set(header):
        raise RuntimeError("rtl-inst table requires module_name, rtl_path, and description")
    records = []
    for row in rows[1:]:
        if len(row) != len(header):
            raise RuntimeError("rtl-inst table has an invalid row")
        records.append(dict(zip(header, row, strict=True)))
    return records


def rtl_inst_rows(source: str) -> list[dict[str, str]]:
    for section in SECTION_RE.finditer(source):
        if section.group("prefix") == RTL_INST_PREFIX:
            return parse_table(section.group("content"))
    return []


def load_rtl_inst(script: Path) -> object:
    if not script.is_file():
        raise RuntimeError(f"gen_rtl_inst script not found: {script}")
    module_name = "_py_rtl_snippet_gen_rtl_inst"
    spec = importlib.util.spec_from_file_location(module_name, script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load gen_rtl_inst: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def generate_rtl_inst_snippets(
    rows: list[dict[str, str]], common_root: Path, rtl_inst_script: Path
) -> dict[str, object]:
    if not rows:
        return {}
    common_root = common_root.resolve()
    if not common_root.is_dir():
        raise RuntimeError(f"com repository not found: {common_root}")
    rtl_inst = load_rtl_inst(rtl_inst_script.resolve())
    snippets: dict[str, object] = {}
    modules: set[str] = set()
    for row in rows:
        module_name = row["module_name"]
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", module_name):
            raise RuntimeError(f"invalid rtl-inst module_name: {module_name}")
        if module_name in modules:
            raise RuntimeError(f"duplicate rtl-inst module_name: {module_name}")
        rtl_path = (common_root / row["rtl_path"]).resolve()
        try:
            rtl_path.relative_to(common_root)
        except ValueError as exc:
            raise RuntimeError(f"rtl-inst path escapes com repository: {row['rtl_path']}") from exc
        if not rtl_path.is_file():
            raise RuntimeError(f"rtl-inst RTL file not found: {rtl_path}")
        rendered, parsed_modules = rtl_inst.render_inst(rtl_path)
        parsed_names = [module.name for module in parsed_modules]
        if parsed_names != [module_name]:
            raise RuntimeError(
                f"rtl-inst expected module '{module_name}', parsed: {', '.join(parsed_names)}"
            )
        rendered = append_ram_shell(rendered, row.get("ram_shell", ""), module_name)
        body = rendered.splitlines()
        if body and body[0].startswith("// Source:"):
            body = body[2:] if len(body) > 1 and not body[1] else body[1:]
        content = "\n".join(body).replace(
            f"u_{module_name}_inst", f"${{2:u_{module_name}_inst}}"
        ).replace("u_inst", "${1:u_inst}")
        snippets[f"RTL instance {module_name}"] = {
            "scope": "systemverilog,verilog",
            "prefix": f"rtl-inst-{module_name}",
            "description": row["description"],
            "body": content.splitlines(),
        }
        modules.add(module_name)
    return snippets


def append_ram_shell(rendered: str, ram_shell: str, module_name: str) -> str:
    if not ram_shell:
        return rendered
    if ram_shell not in {"1p1bank", "1p2bank"}:
        raise RuntimeError(f"invalid ram_shell for '{module_name}': {ram_shell}")
    if module_name != f"com_sync_fifo_ram_{ram_shell}":
        raise RuntimeError(f"ram_shell '{ram_shell}' does not match module '{module_name}'")

    rendered = re.sub(
        r"(?m)^assign u_inst_i_ram_rd_data\s*=\s*i_ram_rd_data;\n?",
        "",
        rendered,
    )
    localparams = (
        "//localparam-----------------------------------------------------------------\n"
        "localparam RAM_DEPTH     = 4;\n"
        "localparam OUT_DEPTH     = 4;\n"
        "localparam RAM_ONE_DEPTH = RAM_DEPTH/2;\n"
        "localparam RAM_ONE_AW    = $clog2(RAM_ONE_DEPTH>2 ? RAM_ONE_DEPTH : 2);\n"
        "localparam TOL_CW        = $clog2(RAM_DEPTH+OUT_DEPTH+1);\n"
    )
    if ram_shell == "1p1bank":
        localparams += "localparam RAM_ONE_DW    = DW*2;\n"
        shell = """

//ram shell instance---------------------------------------------------------
???_ram_shell #(
    .DATA_W (RAM_ONE_DW   ),
    .DEPTH  (RAM_ONE_DEPTH),
    .STRB_W (1            )
)${3:u_com_spram_shell_fifo_ram}
(
    .clk            (clk                    ), //i
    .i_cfg_mem_ctrl (${4:i_cfg_mem_ctrl}     ), //i
    .i_ce_n         (u_inst_o_ram_ce_n      ), //i
    .i_we_n         (u_inst_o_ram_we_n      ), //i
    .i_addr         (u_inst_o_ram_addr      ), //i
    .i_wr_data      (u_inst_o_ram_wr_data   ), //i
    .o_rd_data      (u_inst_i_ram_rd_data   )  //o
);
"""
    else:
        shell = """

//ram shell instance---------------------------------------------------------
???_ram_shell #(
    .DATA_W (DW           ),
    .DEPTH  (RAM_ONE_DEPTH),
    .STRB_W (1            )
)u_com_spram_shell_fifo_ram[1:0]
(
    .clk            (clk                   ), //i
    .i_cfg_mem_ctrl (${3:i_cfg_mem_ctrl}        ), //i
    .i_ce_n         (u_inst_o_ram_ce_n      ), //i
    .i_we_n         (u_inst_o_ram_we_n      ), //i
    .i_addr         (u_inst_o_ram_addr      ), //i
    .i_wr_data      (u_inst_o_ram_wr_data   ), //i
    .o_rd_data      (u_inst_i_ram_rd_data   )  //o
);
"""
    marker = "//signal declare-------------------------------------------------------------\n"
    if marker not in rendered:
        raise RuntimeError(f"rtl-inst output has no signal declaration marker: {module_name}")
    return rendered.replace(marker, localparams + marker, 1).rstrip() + shell


def parse_snippet_markdown(
    input_path: Path,
    common_root: Path = DEFAULT_COMMON_ROOT,
    rtl_inst_script: Path = DEFAULT_RTL_INST_SCRIPT,
) -> dict[str, object]:
    try:
        source = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"failed to read snippet Markdown: {exc}") from exc

    snippets: dict[str, object] = {}
    prefixes: set[str] = set()
    for section in SECTION_RE.finditer(source):
        prefix = section.group("prefix")
        content = section.group("content")
        if prefix == RTL_INST_PREFIX:
            continue
        metadata = {
            match.group("key"): match.group("value")
            for match in META_RE.finditer(content)
        }
        code_match = CODE_BLOCK_RE.search(content)
        if code_match is None:
            raise RuntimeError(f"snippet '{prefix}' has no SystemVerilog code block")
        if prefix in prefixes:
            raise RuntimeError(f"duplicate snippet prefix: {prefix}")

        title = metadata.get("title", prefix)
        if title in snippets:
            raise RuntimeError(f"duplicate snippet title: {title}")
        body = code_match.group("body").rstrip("\r\n").splitlines()
        if not body:
            raise RuntimeError(f"snippet '{prefix}' has an empty code block")
        snippets[title] = {
            "scope": metadata.get("scope", "systemverilog,verilog"),
            "prefix": prefix,
            "description": metadata.get("description", prefix),
            "body": body,
        }
        prefixes.add(prefix)

    integration_snippets = generate_rtl_inst_snippets(
        rtl_inst_rows(source), common_root, rtl_inst_script
    )
    for title, item in integration_snippets.items():
        prefix = str(item["prefix"])
        if title in snippets or prefix in prefixes:
            raise RuntimeError(f"duplicate generated rtl-inst snippet: {prefix}")
        snippets[title] = item
        prefixes.add(prefix)

    if not snippets:
        raise RuntimeError(f"no snippets found in {input_path}")
    return snippets


def load_snippets(
    input_path: Path = SNIPPET_MD_PATH,
    common_root: Path = DEFAULT_COMMON_ROOT,
    rtl_inst_script: Path = DEFAULT_RTL_INST_SCRIPT,
) -> dict[str, object]:
    return parse_snippet_markdown(input_path, common_root, rtl_inst_script)


def write_snippets(snippets: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snippets, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def expand_defaults(body: list[str], cursor_text: str = "") -> list[str]:
    values: dict[str, str] = {}

    def replace_default(match: re.Match[str]) -> str:
        index, value = match.groups()
        values.setdefault(index, value)
        return value

    def replace_reference(match: re.Match[str]) -> str:
        index = match.group(1) or match.group(2)
        if index == "0":
            return "$0"
        return values.get(index, "")

    lines: list[str] = []
    for line in body:
        line = DEFAULT_PLACEHOLDER_RE.sub(replace_default, line)
        line = REFERENCE_PLACEHOLDER_RE.sub(replace_reference, line)
        lines.append(line.replace("$0", cursor_text))
    return lines


def snippet_body(snippets: dict[str, object], title: str, cursor_text: str = "") -> list[str]:
    item = snippets.get(title)
    if not isinstance(item, dict):
        raise RuntimeError(f"snippet not found: {title}")
    body = item.get("body")
    if not isinstance(body, list) or not all(isinstance(line, str) for line in body):
        raise RuntimeError(f"snippet '{title}' has an invalid body")
    return expand_defaults(body, cursor_text)


def title_for_prefix(snippets: dict[str, object], prefix: str) -> str | None:
    for title, item in snippets.items():
        if isinstance(item, dict) and item.get("prefix") == prefix:
            return title
    return None


def generate_preview(snippets: dict[str, object], output_path: Path) -> None:
    sections: list[list[str]] = [
        [
            "// Generated preview for py_rtl_snippet.",
            "// This file expands default placeholders for syntax review only.",
            "",
        ],
    ]
    module_title = title_for_prefix(snippets, "rtl-module")
    if module_title is not None:
        sections.append(snippet_body(snippets, module_title))

    type_titles = [
        title_for_prefix(snippets, prefix)
        for prefix in ("rtl-struct", "rtl-union", "rtl-enum")
    ]
    if all(title is not None for title in type_titles):
        sections.append(
            [
                "package py_rtl_snippet_types_pkg;",
                "",
                *snippet_body(snippets, type_titles[0]),
                "",
                *snippet_body(snippets, type_titles[1]),
                "",
                *snippet_body(snippets, type_titles[2]),
                "",
                "endpackage",
            ]
        )

    for prefix in ALWAYS_PREFIXES:
        title = title_for_prefix(snippets, prefix)
        if title is not None:
            sections.append(snippet_body(snippets, title))

    for prefix in PORT_PREFIXES:
        title = title_for_prefix(snippets, prefix)
        if title is not None:
            sections.append(snippet_body(snippets, title))
    for title, snippet in snippets.items():
        prefix = snippet.get("prefix", "")
        if isinstance(prefix, str) and prefix.startswith("rtl-inst-"):
            sections.append([f"// {prefix}", *snippet_body(snippets, title)])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n\n".join("\n".join(section) for section in sections) + "\n"
    output_path.write_text(content, encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse Markdown RTL snippets and generate VS Code snippet JSON."
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--list", action="store_true", help="list snippet prefixes")
    action.add_argument("--print", action="store_true", help="print generated snippet JSON")
    action.add_argument(
        "--preview",
        type=Path,
        metavar="FILE",
        help="generate a SystemVerilog preview with default placeholders expanded",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=SNIPPET_MD_PATH,
        help="snippet Markdown source, default: input/rtl_snippets.md",
    )
    parser.add_argument("-o", "--output", type=Path, help="generated VS Code snippet JSON")
    parser.add_argument(
        "--common-root",
        type=Path,
        default=DEFAULT_COMMON_ROOT,
        help="com repository root used by the rtl-inst table",
    )
    parser.add_argument(
        "--rtl-inst-script",
        type=Path,
        default=DEFAULT_RTL_INST_SCRIPT,
        help="gen_rtl_inst.py used to build integration snippets",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        snippets = load_snippets(args.input, args.common_root, args.rtl_inst_script)
        if args.preview is not None:
            generate_preview(snippets, args.preview)
            print(f"generated {args.preview} ({len(snippets)} snippets)")
        elif args.output is not None:
            write_snippets(snippets, args.output)
            print(f"generated {args.output} ({len(snippets)} snippets)")
        elif args.print:
            print(json.dumps(snippets, indent=4, ensure_ascii=False))
        else:
            rows = []
            for item in snippets.values():
                if not isinstance(item, dict):
                    raise RuntimeError("snippet entry must be an object")
                rows.append((str(item["prefix"]), str(item["description"])))
            prefix_width = max(len(prefix) for prefix, _ in rows)
            for prefix, description in rows:
                print(f"{prefix:<{prefix_width}}  {description}")
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
