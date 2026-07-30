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
        checkout="../groups/py_tools_for_hw",
        workspace="../..",
    ),
    RepositorySpec(
        name="com",
        repository="https://github.com/damagebro/com.git",
        branch="main",
        checkout="../groups/com",
    ),
)

REPOSITORY_MAP = {repository.name: repository for repository in REPOSITORY_SPECS}


TOOL_SPECS = (
    ToolSpec(
        name="mem_tool",
        script="impl_template/memory/mem_tool/src/main.py",
        description="Generate memory shells, reports, and integration RTL.",
        usage="hw_tool de mem_tool [options]",
        doc_url="https://github.com/damagebro/com/blob/main/impl_template/memory/mem_tool/README.md",
        readme="impl_template/memory/mem_tool/README.md",
        repository_name="com",
    ),
    ToolSpec(
        name="rtl_inst",
        script="gen_rtl_inst/src/gen_rtl_inst.py",
        description="Generate RTL integration instance snippets.",
        usage="hw_tool de rtl_inst <rtl_path> [-o inst.sv]",
        doc_url="https://github.com/damagebro/py_tools_for_hw/blob/main/gen_rtl_inst/README.md",
        readme="gen_rtl_inst/README.md",
        repository_name="py_tools_for_hw",
    ),
    ToolSpec(
        name="rtl_dummy",
        script="gen_rtl_dummy/src/gen_rtl_dummy.py",
        description="Generate bbox, stub, or port-swap RTL dummy modules.",
        usage="hw_tool de rtl_dummy <rtl_path> [-m bbox|stub|port_swap] [-o dummy.sv]",
        doc_url="https://github.com/damagebro/py_tools_for_hw/blob/main/gen_rtl_dummy/README.md",
        readme="gen_rtl_dummy/README.md",
        repository_name="py_tools_for_hw",
    ),
    ToolSpec(
        name="csr_tool",
        script="csr_tool/src/autogen_reg.py",
        description="Generate CSR RTL, documentation, testbench, and firmware files.",
        usage="hw_tool de csr_tool -i <register.md> [--nested] [-o out]",
        doc_url="https://github.com/damagebro/py_tools_for_hw/blob/main/csr_tool/README.md",
        readme="csr_tool/README.md",
        repository_name="py_tools_for_hw",
    ),
    ToolSpec(
        name="gen_tb",
        script="py_rtl_sim/gen_tb_demo/gen_tb.py",
        description="Generate a standalone RTL simulation testbench directory.",
        usage="hw_tool de gen_tb [-o sim] [-top <module>] [-f <filelist>]",
        doc_url="https://github.com/damagebro/py_tools_for_hw/blob/main/py_rtl_sim/gen_tb_demo/README.md",
        readme="py_rtl_sim/gen_tb_demo/README.md",
        repository_name="py_tools_for_hw",
    ),
)

TOOL_MAP = {tool.name: tool for tool in TOOL_SPECS}
DEFAULT_GROUP = None
