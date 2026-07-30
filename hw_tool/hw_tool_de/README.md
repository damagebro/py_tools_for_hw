# hw_tool_de

`hw_tool_de` 是 Digital Engineering 小组的工具入口。它仅保存入口、注册表和测试；业务工具继续位于 `py_tools_for_hw/` 根目录，既可由公司级 `hw_tool` 调用，也可独立运行。

## 已注册工具

| tool        | source_path                                                | 说明                                  |
| ----------- | ---------------------------------------------------------- | ------------------------------------- |
| `mem_tool`  | `com:impl_template/memory/mem_tool/src/main.py`            | 生成 memory shell、报告和集成 RTL     |
| `rtl_inst`  | `py_tools_for_hw:gen_rtl_inst/src/gen_rtl_inst.py`         | 生成 RTL 集成例化片段                 |
| `rtl_dummy` | `py_tools_for_hw:gen_rtl_dummy/src/gen_rtl_dummy.py`       | 生成 bbox、stub 或 port_swap 挖空 RTL |
| `csr_tool`  | `py_tools_for_hw:csr_tool/src/autogen_reg.py`              | 生成 CSR RTL、文档、TB 和 Firmware    |
| `gen_tb`    | `py_tools_for_hw:py_rtl_sim/gen_tb_demo/gen_tb.py`         | 生成独立仿真 testbench 目录           |

## 工具来源仓库

`rtl_inst`、`rtl_dummy`、`csr_tool` 和 `gen_tb` 共用 `py_tools_for_hw` Git URL 与一个 checkout；`mem_tool` 使用独立的 `com` Git URL。注册表只记录仓库内相对路径，`sync --all` 会按来源仓库去重，同一仓库只同步一次。

当前开发工作区存在时，`hw_tool_de` 优先直接使用它，不会 clone 自身仓库。将 `hw_tool_de` 拆分为独立仓库后，缺少本地工作区时会自动使用 `hw_tool/groups/py_tools_for_hw/` 中由 `sync` 拉取的 checkout。

## 调用方式

公司级调用：

```bash
hw_tool de list
hw_tool de rtl_dummy path/to/source.sv -m port_swap -o dummy.sv
```

首次使用独立部署的来源仓库前执行：

```bash
hw_tool de sync csr_tool
```

它会 clone 到 `hw_tool/groups/py_tools_for_hw/`；`mem_tool` 会 clone 到 `hw_tool/groups/com/`。后续可使用 `hw_tool de sync <tool>` 或 `hw_tool sync --all` 更新。

直接调用：

```bash
python -B src/hw_tool_de.py list
python -B src/hw_tool_de.py csr_tool -i register.md --nested -o out
```

Windows 可将 `hw_tool_de/bin` 加入 `PATH` 后使用 `hw_tool_de.cmd`；Linux 使用 `hw_tool_de/bin/hw_tool_de`。

## 新增 DE 工具

在 [tool_registry.py](src/tool_registry.py) 中先新增或复用一条 `RepositorySpec`，再在 `ToolSpec` 中配置 `repository_name` 和仓库内相对路径。普通 Python CLI 保持默认 `kind="script"`；仅当 DE 下继续划分子团队时才使用 `kind="hub"` 和 `tool_home`。
