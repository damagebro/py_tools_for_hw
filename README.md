# HW Tool

面向芯片前端与 RTL 开发的工具集，支持命令行独立使用、通过 HW Tool Hub 统一调用，以及通过 VS Code 插件交互使用。

## 工具一览

| 工具与文档                                  | 简介                                                            |
| ------------------------------------------- | --------------------------------------------------------------- |
| [hw_tool](hw_tool/README.md)                | 统一工具入口；可集成其他 group，也可被上层 Hub 集成。           |
| [git_repo_mgr](git_repo_mgr/README.md)      | 管理 Git 仓库依赖，支持同步、版本冲突检查与批量操作。           |
| [rtl_flist_mgr](rtl_flist_mgr/README.md)    | 解析 core 依赖，结合 TOML、.core 与 legacy.f 生成多模式 flist。 |
| [csr_tool](csr_tool/README.md)              | 从 Markdown / Excel 生成 RTL、文档、UVM RAL 与 C Header。       |
| [mem_tool](mem_tool/README.md)              | 整理 SRAM 需求，生成 memory shell 并集成 PHY。                  |
| [gen_rtl_inst](gen_rtl_inst/README.md)      | 提取 RTL 模块参数和端口，生成例化代码片段。                     |
| [gen_rtl_dummy](gen_rtl_dummy/README.md)    | 生成 bbox、stub 或端口方向交换的 RTL 模块。                     |
| [py_rtl_snippet](py_rtl_snippet/README.md)  | 生成语句、总线端口及 Common IP 例化 snippet。                   |
| [gen_tb](py_rtl_sim/gen_tb_demo/README.md)  | 生成包含 testbench、filelist、环境脚本与 Makefile 的仿真框架。  |
| [py_md2html](py_md2html/README.md)          | 将 Markdown 转为 HTML，提供目录和主题等阅读功能。               |

## 快速开始

1. 在VS Code中安装HW Tool扩展（支持通过VSIX安装）。
2. 准备Python 3.11+，安装依赖：`python -m pip install jinja2 openpyxl Markdown`。
3. 按`Ctrl+Shift+P`输入`HW Tool:`选择命令，或使用对应文件的编辑器右键菜单。
4. 编辑Verilog/SystemVerilog时，输入`rtl-`使用代码片段。

插件内置工具源码，生成类命令调用本机Python；代码片段展开无需Python。Python不在PATH时，通过`dmgHwTool.pythonPath`指定解释器。

完整命令、配置与安装方式见[VS Code扩展说明](hw_tool/publish/vscode/README.md)。

## 更多资源

- **总线验证示例**：[AXI VIP](py_rtl_sim/sim_axi_vip/README.md)、[APB VIP](py_rtl_sim/sim_apb_vip/README.md)、[AHB-Lite VIP](py_rtl_sim/sim_ahb_vip/README.md)。
- **命令行与发布**：[HW Tool CLI](hw_tool/README.md)、[发布说明](hw_tool/publish/README.md)。
- **配套RTL库**：[com仓库][com-repo]提供Common IP、AXI/DMA和CSR bus模块，可与本工具集生成的RTL配套集成。
- **配套文档**：[CSR bus][com-csr]、[工艺模板][com-impl]、[Common IP][com-common]。

[com-csr]: https://github.com/damagebro/com/blob/main/doc/common_rtl_csr_manual.md
[com-impl]: https://github.com/damagebro/com/blob/main/impl_template/README.md
[com-common]: https://github.com/damagebro/com/blob/main/doc/common_rtl_manual.md
[com-repo]: https://github.com/damagebro/com
