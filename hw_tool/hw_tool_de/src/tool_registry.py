from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    script: str
    description: str
    usage: str
    kind: str = "script"
    tool_home: str | None = None
    source: str = "local"
    repository: str | None = None
    branch: str | None = None
    doc_url: str | None = None
    readme: str | None = None
    checkout: str | None = None
    repository_name: str | None = None
    doctor_packages: tuple[str, ...] = ()
    example: str | None = None
    smoke_args: tuple[str, ...] = ()
    smoke_outputs: tuple[str, ...] = ()
    smoke_stdout: tuple[str, ...] = ()
    unit_tests: tuple[str, ...] = ()
    unit_cwd: str | None = None
    contract_enabled: bool = True


@dataclass(frozen=True)
class RepositorySpec:
    name: str
    repository: str
    branch: str
    checkout: str
    workspace: str | None = None


REPOSITORY_SPECS = (
    RepositorySpec(
        name="py_tools_for_hw",
        repository="https://github.com/damagebro/py_tools_for_hw.git",
        branch="main",
        checkout="../repository/py_tools_for_hw",
        workspace="../..",
    ),
    RepositorySpec(
        name="com",
        repository="https://github.com/damagebro/com.git",
        branch="main",
        checkout="../repository/com",
        workspace="../../../com",
    ),
)

REPOSITORY_MAP = {repository.name: repository for repository in REPOSITORY_SPECS}
HUB_ID = "py_tools_for_hw.de"


TOOL_SPECS = (
    ToolSpec(
        name="mem_tool",
        script="impl_template/memory/mem_tool/src/main.py",
        description="Generate memory shells, reports, and integration RTL.",
        usage="hw_tool de mem_tool [options]",
        doc_url="https://github.com/damagebro/com/blob/main/impl_template/memory/mem_tool/README.md",
        readme="impl_template/memory/mem_tool/README.md",
        repository_name="com",
        contract_enabled=False,
    ),
    ToolSpec(
        name="rtl_inst",
        script="gen_rtl_inst/src/gen_rtl_inst.py",
        description="Generate RTL integration instance snippets.",
        usage="hw_tool de rtl_inst <rtl_path> [-o inst.sv]",
        doc_url="https://github.com/damagebro/py_tools_for_hw/blob/main/gen_rtl_inst/README.md",
        readme="gen_rtl_inst/README.md",
        repository_name="py_tools_for_hw",
        example="gen_rtl_inst/test/test.sv",
        smoke_args=("{example}", "-o", "{output}/inst.sv"),
        smoke_outputs=("inst.sv",),
        unit_tests=("gen_rtl_inst/test/test_gen_rtl_inst.py",),
        unit_cwd="gen_rtl_inst",
    ),
    ToolSpec(
        name="rtl_dummy",
        script="gen_rtl_dummy/src/gen_rtl_dummy.py",
        description="Generate bbox, stub, or port-swap RTL dummy modules.",
        usage="hw_tool de rtl_dummy <rtl_path> [-m bbox|stub|port_swap] [-o dummy.sv]",
        doc_url="https://github.com/damagebro/py_tools_for_hw/blob/main/gen_rtl_dummy/README.md",
        readme="gen_rtl_dummy/README.md",
        repository_name="py_tools_for_hw",
        example="gen_rtl_dummy/test/sample_rtl.sv",
        smoke_args=("{example}", "-m", "bbox", "-o", "{output}/dummy.sv"),
        smoke_outputs=("dummy.sv",),
        unit_tests=("gen_rtl_dummy/test/test_gen_rtl_dummy.py",),
        unit_cwd="gen_rtl_dummy",
    ),
    ToolSpec(
        name="csr_tool",
        script="csr_tool/src/autogen_reg.py",
        description="Generate CSR RTL, documentation, testbench, and firmware files.",
        usage="hw_tool de csr_tool -i <register.md> [--nested] [-o out]",
        doc_url="https://github.com/damagebro/py_tools_for_hw/blob/main/csr_tool/README.md",
        readme="csr_tool/README.md",
        repository_name="py_tools_for_hw",
        doctor_packages=("jinja2", "openpyxl"),
        example="csr_tool/input/top_reg.md",
        smoke_args=("-i", "{example}", "--nested", "-o", "{output}"),
        smoke_outputs=(
            "doc/top_tree.md",
            "rtl/top.sv",
            "firmware/top_all_reg_addr.h",
        ),
        unit_tests=("csr_tool/test_parser.py",),
        unit_cwd="csr_tool",
    ),
    ToolSpec(
        name="gen_tb",
        script="py_rtl_sim/gen_tb_demo/gen_tb.py",
        description="Generate a standalone RTL simulation testbench directory.",
        usage="hw_tool de gen_tb [-o sim] [-top <module>] [-f <filelist>]",
        doc_url="https://github.com/damagebro/py_tools_for_hw/blob/main/py_rtl_sim/gen_tb_demo/README.md",
        readme="py_rtl_sim/gen_tb_demo/README.md",
        repository_name="py_tools_for_hw",
        example="py_rtl_sim/gen_tb_demo/examples/basic/README.md",
        smoke_args=("-o", "{output}/sim", "-top", "smoke_top"),
        smoke_outputs=("sim/Makefile", "sim/ENV.sh", "sim/tb/top.sv"),
        unit_tests=("py_rtl_sim/gen_tb_demo/test/test_gen_tb.py",),
        unit_cwd="py_rtl_sim/gen_tb_demo",
    ),
    ToolSpec(
        name="git_repo_mgr",
        script="git_repo_mgr/src/git_repo_mgr.py",
        description="Manage recursive multi-Git workspace dependencies.",
        usage="hw_tool de git_repo_mgr <command> [options]",
        doc_url="https://github.com/damagebro/py_tools_for_hw/blob/main/git_repo_mgr/README.md",
        readme="git_repo_mgr/README.md",
        repository_name="py_tools_for_hw",
        example="git_repo_mgr/README.md",
        smoke_args=("--help",),
        smoke_stdout=("Manage a recursively declared multi-Git workspace.",),
        unit_tests=("git_repo_mgr/test/test_git_repo_mgr.py",),
        unit_cwd="git_repo_mgr",
    ),
    ToolSpec(
        name="rtl_flist_mgr",
        script="rtl_flist_mgr/src/rtl_flist_mgr.py",
        description="Resolve distributed RTL cores into deterministic filelists.",
        usage="hw_tool de rtl_flist_mgr <core_file> -o <output.f> [-m sim|synth|lint|emu|fpga] [options]",
        doc_url="https://github.com/damagebro/py_tools_for_hw/blob/main/rtl_flist_mgr/README.md",
        readme="rtl_flist_mgr/README.md",
        repository_name="py_tools_for_hw",
        example="rtl_flist_mgr/README.md",
        smoke_args=("--help",),
        smoke_stdout=("Generate a deterministic RTL filelist from one core file.",),
        unit_tests=("rtl_flist_mgr/test/test_rtl_flist_mgr.py",),
        unit_cwd="rtl_flist_mgr",
    ),
)

TOOL_MAP = {tool.name: tool for tool in TOOL_SPECS}
DEFAULT_GROUP = None
