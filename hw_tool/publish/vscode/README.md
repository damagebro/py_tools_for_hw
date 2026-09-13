# HW Tool

面向芯片前端与 RTL 开发的工具集，支持命令行独立使用、HW Tool Hub 统一调用和 VS Code 插件交互。

插件内置工具源码，不需要另行部署 `hw_tool` 或配置其 PATH。生成类命令调用本机 Python；代码片段展开无需 Python。Common IP 例化已固化在插件中，使用时不访问 com 仓库。

## 工具一览

| 工具与文档                                                                                        | 简介                                                            |
| ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| [hw_tool](https://github.com/damagebro/py_tools_for_hw/blob/main/hw_tool/README.md)               | 统一工具入口；可集成其他 group，也可被上层 Hub 集成。           |
| [git_repo_mgr](https://github.com/damagebro/py_tools_for_hw/blob/main/git_repo_mgr/README.md)     | 管理 Git 仓库依赖，支持同步、版本冲突检查与批量操作。           |
| [rtl_flist_mgr](https://github.com/damagebro/py_tools_for_hw/blob/main/rtl_flist_mgr/README.md)   | 解析 core 依赖，结合 TOML、.core 与 legacy.f 生成多模式 flist。 |
| [csr_tool](https://github.com/damagebro/py_tools_for_hw/blob/main/csr_tool/README.md)             | 从 Markdown / Excel 生成 RTL、文档、UVM RAL 与 C Header。       |
| [mem_tool](https://github.com/damagebro/py_tools_for_hw/blob/main/mem_tool/README.md)             | 整理 SRAM 需求，生成 memory shell 并集成 PHY。                  |
| [gen_rtl_inst](https://github.com/damagebro/py_tools_for_hw/blob/main/gen_rtl_inst/README.md)     | 提取 RTL 模块参数和端口，生成例化代码片段。                     |
| [gen_rtl_dummy](https://github.com/damagebro/py_tools_for_hw/blob/main/gen_rtl_dummy/README.md)   | 生成 bbox、stub 或端口方向交换的 RTL 模块。                     |
| [py_rtl_snippet](https://github.com/damagebro/py_tools_for_hw/blob/main/py_rtl_snippet/README.md) | 生成语句、总线端口及 Common IP 例化 snippet。                   |
| [gen_tb](https://github.com/damagebro/py_tools_for_hw/blob/main/py_rtl_sim/gen_tb_demo/README.md) | 生成包含 testbench、filelist、环境脚本与 Makefile 的仿真框架。  |
| [py_md2html](https://github.com/damagebro/py_tools_for_hw/blob/main/py_md2html/README.md)         | 将 Markdown 转为 HTML，提供目录和主题等阅读功能。               |

## 快速开始

1. 在 VS Code 扩展中搜索 `@id:damagebro.dmg-hw-tool` 安装，也可通过 VSIX 安装。
2. 准备 Python 3.11+，安装依赖：

```bash
python -m pip install jinja2 openpyxl Markdown
```

3. 按 `Ctrl+Shift+P`，输入 `HW Tool:` 选择命令，也可使用对应文件的右键菜单。
4. 编辑 Verilog/SystemVerilog 时输入 `rtl-`，选择代码片段。

默认自动依次尝试 `python`、`python3`，Windows 再尝试 `py -3`，选择首个满足 Python 3.11+ 的解释器。也可在 VS Code 设置中指定：

```json
{
  "dmgHwTool.pythonPath": "C:/Python311/python.exe"
}
```

该设置留空时自动查找；明确配置后仅使用该解释器，不可用或版本过低时报错，不自动回退。依赖缺失时提示在选中的解释器中安装，不切换环境或自动安装。

## 命令速查

以下命令均带 `HW Tool:` 前缀，代码片段除外。RTL 操作支持 `.v/.sv`；生成前请保存当前输入。

| 工具               | 命令或入口                                | 说明                                                               |
| ------------------ | ----------------------------------------- | ------------------------------------------------------------------ |
| **通用功能**       | `Open Tool Documentation...`              | 选择工具 README，以 HTML 预览。                                    |
|                    | `Change Preview Theme...`                 | 切换浅色、深色或跟随 VS Code 的预览主题。                          |
|                    | `Convert Markdown to HTML...`             | 当前 Markdown 转 HTML，自动加目录和编号；覆盖前确认。              |
|                    | `Preview Markdown as HTML...`             | 直接预览当前 Markdown，不写 HTML。                                 |
| **py_rtl_snippet** | 输入 `rtl-` 前缀                          | 语句、总线端口及 `rtl-inst-<module>` 常用 IP 例化。                |
| **rtl_inst**       | `Replace Selected RTL Path With Instance` | 选中绝对 RTL 路径后替换为例化；失败不修改选区。                    |
|                    | `Insert RTL Instance From File...`        | 选择 RTL 文件，在光标处插入例化。                                  |
|                    | `Copy RTL Instance`                       | 当前或 Explorer 选中 RTL 的例化复制到剪贴板。                      |
| **rtl_dummy**      | `Generate RTL Dummy...`                   | 选择 bbox/stub/port_swap，输出到源文件旁 `out/rtl_dummy/`。        |
| **gen_tb**         | `Generate Empty TB Environment`           | 在 Terminal cwd 的 `out/sim/` 生成空 TB 环境。                     |
|                    | `Generate TB From Current Filelist...`    | 选择 `.f`，输入 DUT top，输出到 filelist 旁 `out/sim/`。           |
| **mem_tool**       | `Open Memory Tool Documentation`          | 以 HTML 预览 Memory Tool 文档。                                    |
|                    | `Generate Memory Shell...`                | 输入 shell prefix，在 Terminal cwd 的 `out/mem_tool/` 生成 shell。 |
|                    | `Integrate Memory From Excel`             | 选择 `.xlsx`，输入 shell prefix，集成 memory PHY。                 |
| **csr_tool**       | `Open CSR Documentation`                  | 以 HTML 预览 CSR 文档。                                            |
|                    | `Create CSR Template...`                  | 选择 Markdown/Excel 及是否包含 `base_info`，创建寄存器模板。       |
|                    | `Create Default CSR Template`             | 直接创建仅含 `reg_define` 的 Markdown 模板。                       |
|                    | `Generate CSR (Single)`                   | 当前 CSR Markdown/Excel 生成单模块，输出到输入旁 `out/`。          |
|                    | `Generate CSR (Nested)`                   | 生成多层 CSR，输出到输入旁 `out/`，可打开寄存器树。                |
|                    | `Open CSR Tree HTML`                      | 预览当前输入对应的 `out/doc/*_tree.html`。                         |
|                    | `Insert CSR Register Row...`              | 只选择寄存器类型，插入默认行后自行编辑。                           |
| **rtl_flist_mgr**  | `Set RTL Workspace Root...`               | 选择根目录、初始化标记并刷新 core 列表。                           |
|                    | `Generate RTL Filelist...`                | 选择模式，刷新索引，输出到 core 旁 `out/flist/`。                  |
|                    | `Refresh RTL Core List`                   | 在 RTL Cores 视图列出本体 core，不含 import；点击打开。            |
| **git_repo_mgr**   | `Create Git Dependencies`                 | 在 Terminal cwd 创建并打开 `git_deps.toml`；已存在则直接打开。     |
|                    | `Git Repository Status`                   | 显示分支/ref、commit、状态及异常明细；需先 sync。                  |
|                    | `Sync Git Repositories...`                | 选择 full/shallow，确认后同步；保留已有 checkout。                 |

## 目录与使用约定

- **Terminal cwd**：Git 依赖模板、空 TB 和 Memory Shell 严格使用当前激活 Terminal 的 Shell Integration cwd；无法获取时提示停止，不回退到其他目录。
- **CSR 模板**：优先 Terminal cwd，其次当前文件目录、workspace 根目录。Excel 使用 Office/WPS 打开以保留下拉菜单。
- **Memory prefix**：输入的 prefix 控制 SRAM shell 命名；Excel 中的 prefix 控制 wrapper/PHY 命名，两者独立。
- **RTL flist**：默认输出绝对路径，生成时刷新索引；文件名为 `<core_name>_<mode>.f`。
- **Git 管理**：status、sync 查找 workspace。CLEAN 仅表示无本地改动，不代表远端最新；sync 不自动 pull 或切换已有 checkout 版本。graph、forall、switch、tag、快照及 admin/release 操作保留在 Terminal。

## 更多资源

- **飞书文档**：[HW Tool 文档中心](https://my.feishu.cn/wiki/XwJPwteoEiu9hNkGCfkcvLaynGc)。
- **命令行与发布**：[HW Tool CLI](https://github.com/damagebro/py_tools_for_hw/blob/main/hw_tool/README.md)、[发布说明](https://github.com/damagebro/py_tools_for_hw/blob/main/hw_tool/publish/README.md)。
- **配套RTL库**：[com仓库][com-repo]提供Common IP、AXI/DMA和CSR bus模块，可与本工具集生成的RTL配套集成。
- **配套文档**：[CSR bus][com-csr]、[工艺模板][com-impl]、[Common IP][com-common]。

[com-csr]: https://github.com/damagebro/com/blob/main/doc/common_rtl_csr_manual.md
[com-impl]: https://github.com/damagebro/com/blob/main/impl_template/README.md
[com-common]: https://github.com/damagebro/com/blob/main/doc/common_rtl_manual.md
[com-repo]: https://github.com/damagebro/com


## 许可证

[MIT License](https://github.com/damagebro/py_tools_for_hw/blob/main/hw_tool/publish/vscode/LICENSE.md)：允许使用、修改、商用和再分发，需保留版权及许可声明。第三方组件遵循各自许可证。
