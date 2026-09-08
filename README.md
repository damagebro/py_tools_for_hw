# HW Tool

面向芯片前端与RTL开发的VS Code工具集。直接在编辑器中生成CSR、集成SRAM、插入RTL例化、搭建testbench，并管理filelist与Git仓库依赖。

## 主要功能

| 功能          | 用途与工具文档                                                                                              |
| ------------- | ----------------------------------------------------------------------------------------------------------- |
| CSR寄存器     | 从Markdown/Excel生成RTL、文档、UVM RAL与C Header。[CSR Tool](csr_tool/README.md) · [配套CSR bus][com-csr]   |
| SRAM集成      | 生成memory shell、整理SRAM需求并集成PHY。[Memory Tool](mem_tool/README.md) · [配套工艺模板][com-impl]       |
| RTL例化与占位 | 提取模块端口，插入例化或生成替代模块。[Instance](gen_rtl_inst/README.md) · [Dummy](gen_rtl_dummy/README.md) |
| RTL代码片段   | 输入`rtl-`展开语句、总线端口和常用模块例化。[Snippets](py_rtl_snippet/README.md) · [Common IP][com-common]  |
| 仿真环境      | 生成带top、filelist与环境脚本的独立testbench。[TB生成器](py_rtl_sim/gen_tb_demo/README.md)                  |
| RTL Filelist  | 递归解析core依赖，生成sim/synth/lint使用的.f文件。[Filelist Manager](rtl_flist_mgr/README.md)               |
| 多仓库管理    | 同步Git依赖、检查仓库状态与查看依赖图。[Repository Manager](git_repo_mgr/README.md)                         |
| Markdown预览  | 直接预览HTML，或导出带目录和主题的HTML文件。[Markdown to HTML](py_md2html/README.md)                        |

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

[com-csr]: https://github.com/damagebro/com/blob/main/doc/common_rtl_csr_manual.md
[com-impl]: https://github.com/damagebro/com/blob/main/impl_template/README.md
[com-common]: https://github.com/damagebro/com/blob/main/doc/common_rtl_manual.md
[com-repo]: https://github.com/damagebro/com
