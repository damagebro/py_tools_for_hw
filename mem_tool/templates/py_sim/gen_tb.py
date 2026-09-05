from __future__ import annotations

import argparse
from pathlib import Path
import re
import tempfile


TOP_START_MARKER = "// AUTO_TOP_INST_BEGIN"
TOP_END_MARKER = "// AUTO_TOP_INST_END"
SHELL_START_MARKER = "// AUTO_MEM_SHELL_FILELIST_BEGIN"
SHELL_END_MARKER = "// AUTO_MEM_SHELL_FILELIST_END"
FILELIST_START_MARKER = "// AUTO_USER_FILELIST_BEGIN"
FILELIST_END_MARKER = "// AUTO_USER_FILELIST_END"
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=path.parent,
    ) as handle:
        handle.write(content)
        tmp_path = Path(handle.name)
    tmp_path.replace(path)


def sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def parse_env_items(sim_env: list[str] | tuple[str, ...]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in sim_env:
        if "=" not in item:
            raise ValueError(f"sim env must use NAME=VALUE format: {item}")
        name, value = item.split("=", 1)
        if not ENV_NAME_RE.match(name):
            raise ValueError(f"invalid sim env name: {name}")
        parsed[name] = value
    return parsed


def render_env(sim_env: dict[str, str] | None = None) -> str:
    env_lines = "\n"
    if sim_env:
        env_lines = "\n".join(
            f"export {name}={sh_quote(value)}" for name, value in sim_env.items()
        )
        env_lines = f"{env_lines}\n"
    return f"""SCP_PATH=`pwd`
export SIM_DIR=$SCP_PATH
{env_lines}
if [ ! -d "./bin/" ]
then
    mkdir ./bin/
fi

echo "SIM_DIR=$SIM_DIR"
"""


def render_makefile() -> str:
    return """SHELL := /bin/bash

TC ?= vadd_oneblk
ENV_TC_DIR = ../tc/

RTL_F = ../rtl.f
ENV_F = ../testbench.f

#snps####################################################################################
# vcs -full64 -sverilog -debug_all -lca -kdb -timescale=1ns/1ps -f rtl.f -f testbench.f -top top
SNPS_DEF = +define+DUMP_FSDB

COM_OPT = -l ./compile.log  -Mdir=./csrc \\
-full64 \\
-sverilog \\
-timescale=1ns/100ps \\
-LDFLAGS -Wl,--no-as-needed \\
-kdb \t\\
-lca \t\\
-debug_access+all+reverse \\
-work mylib\t\\
-o\tsimv\t\\
$(SNPS_DEF)

RUN_OPT = \\
+vcs+initreg+0\t\\
+vcs+initmem+0\t\\
-l ./run.log \\
$(SNPS_DEF)

#snps target####################################################################################
help:
\t@echo "make clean "
\t@echo "make com "
\t@echo "make run "
\t@echo "make verdi "
\t@echo "make run TC=${TC} "
\t@echo "#cdns#################"
\t@echo "make sim"
\t@echo "make cdns_com"

clean:
\trm ./bin/ -rf; source ./ENV.sh

com:
\tsource ./ENV.sh; cd ./bin/; vcs  $(COM_OPT)\t-top top -f $(RTL_F) -f $(ENV_F) -assert svaext

run:
\tsource ./ENV.sh; cd ./bin/; ./simv $(RUN_OPT) +TC_DIR=${ENV_TC_DIR} +TC_NAME=${TC}

all: clean com run

verdi:
\tsource ./ENV.sh; cd ./bin/; verdi -top top -f $(RTL_F) -f $(ENV_F) -ssf run.fsdb -sverilog -2009 -full64 &

#cdns####################################################################################
CDNS_DEF = +define+ADD_REPORT
CDNS_OPT = -64bit -sv -access rwc -timescale 1ns/100ps -vlog_ext +.h $(CDNS_DEF) -loadpli1 debpli:novas_pli_boot

#cdns target####################################################################################
sim:
\tsource ./ENV.sh; cd ./bin; xrun $(CDNS_OPT) -top top -f $(RTL_F) -f $(ENV_F) -gui &

cdns_com:
\tsource ./ENV.sh; cd ./bin; xrun $(CDNS_OPT) -elaborate -top top -f $(RTL_F) -f $(ENV_F)
"""


def render_rtl_f(filelist: str | None = None) -> str:
    user_filelist = f"-f {filelist}\n" if filelist else ""
    return f"""//--------------------------------------
//define
//--------------------------------------

//--------------------------------------
//implement (stdcell/sram)
//--------------------------------------
{SHELL_START_MARKER}
{SHELL_END_MARKER}

//--------------------------------------
//project
//--------------------------------------
{FILELIST_START_MARKER}
{user_filelist}{FILELIST_END_MARKER}
"""


def render_testbench_f() -> str:
    return "${SIM_DIR}/tb/top.sv\n"


def render_top(top_module: str | None = None) -> str:
    top_inst = f"{top_module} u_{top_module}();\n" if top_module else ""
    return f"""module top();

{TOP_START_MARKER}
{top_inst}{TOP_END_MARKER}

initial begin
    #100;
    $finish();
end

`ifdef DUMP_FSDB
initial begin
    $fsdbDumpfile("run.fsdb");
    $fsdbDumpMDA(0, top);
    $fsdbDumpvars(0, top);
    $fsdbDumpvars(top, "+all");
    $fsdbDumpon();
end
`endif

endmodule
"""


def generate_tb(
    output: str | Path,
    *,
    top_module: str | None = None,
    filelist: str | None = None,
    sim_env: dict[str, str] | None = None,
) -> list[Path]:
    output = Path(output)
    outputs = [
        output / "ENV.sh",
        output / "Makefile",
        output / "rtl.f",
        output / "testbench.f",
        output / "tb" / "top.sv",
    ]
    atomic_write_text(output / "ENV.sh", render_env(sim_env))
    atomic_write_text(output / "Makefile", render_makefile())
    atomic_write_text(output / "rtl.f", render_rtl_f(filelist))
    atomic_write_text(output / "testbench.f", render_testbench_f())
    atomic_write_text(output / "tb" / "top.sv", render_top(top_module))
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a standalone memory-tool sim testbench sandbox."
    )
    parser.add_argument(
        "-o",
        "--output",
        default="sim",
        help="output sim directory, default: ./sim",
    )
    parser.add_argument(
        "-top",
        "-t",
        "--top_module",
        default=None,
        help="optional DUT top module to instantiate in tb/top.sv",
    )
    parser.add_argument(
        "-f",
        "--filelist",
        default=None,
        help="optional project filelist inserted into rtl.f",
    )
    parser.add_argument(
        "-e",
        "--sim_env",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="environment variable exported by ENV.sh; can be specified multiple times",
    )
    args = parser.parse_args()
    outputs = generate_tb(
        args.output,
        top_module=args.top_module,
        filelist=args.filelist,
        sim_env=parse_env_items(args.sim_env),
    )
    for path in outputs:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
