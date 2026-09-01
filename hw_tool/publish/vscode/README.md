# HW Tool VS Code 发布

本扩展是 `hw_tool` 的编辑器交互层。打包时会把已注册工具源码复制到插件内部的 `runtime/hw_tool/`；CSR 生成直接调用该 runtime，不要求用户另行部署 `hw_tool` 或配置 `PATH`。SystemVerilog snippets 由仓库中的 `py_rtl_snippet` 生成后打包进扩展。

## 当前功能与命令

按 `Ctrl+Shift+P` 打开命令面板，输入 `HW Tool:` 可查看全部命令。编辑器右键菜单提供 Markdown/CSR 命令及 RTL instance 插入或复制；`.v/.sv` 的编辑器和 Explorer 右键菜单均可调用对应 RTL 工具。

| 工具/功能组        | VS Code 命令或入口                                 | 使用条件                           | 说明                                                                                                    |
| ------------------ | -------------------------------------------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------- |
| **通用功能**       | `HW Tool: Open Tool Documentation...`              | Python 环境依赖已安装              | 从已注册工具中选择 README，转换为 HTML 后在 Webview 中打开。                                            |
|                    | `HW Tool: Change Preview Theme...`                 | 无                                 | 设置文档和 Markdown HTML 预览主题，可选 `Light`、`Dark` 或 `Follow VS Code`。                           |
|                    | `HW Tool: Convert Markdown to HTML...`             | 当前文件为 `.md/.markdown`         | 选择是否生成目录，在 Markdown 同目录输出同名 `.html`，随后在 Webview 中打开；也可从编辑器右键菜单调用。 |
| **py_rtl_snippet** | 输入 `rtl-` 前缀                                   | 当前文件为 `.v/.sv`                | 由 VS Code 原生补全列出代码片段，选中后按 `Tab` 展开。                                                  |
| **rtl_inst**       | `HW Tool: Replace Selected RTL Path With Instance` | `.v/.sv` 中选中绝对 RTL 路径       | 调用 `rtl_inst --stdout`，成功后用 instance snippet 一次性替换选区；失败时选区保持不变。                |
|                    | `HW Tool: Insert RTL Instance From File...`        | 当前文件为 `.v/.sv`                | 图形选择一个 `.v/.sv` 文件，在当前光标位置插入 instance snippet。                                       |
|                    | `HW Tool: Copy RTL Instance`                       | 当前或 Explorer 选中 `.v/.sv`      | 自动使用当前文件或 Explorer 右键文件，生成 instance 并写入剪贴板，用户使用 `Ctrl+V` 粘贴。              |
| **rtl_dummy**      | `HW Tool: Generate RTL Dummy...`                   | 当前或 Explorer 选中 `.v/.sv`      | 只选择一次 `bbox/stub/port_swap`，生成到源文件旁的 `out/rtl_dummy/`，随后打开结果文件。                 |
| **gen_tb**         | `HW Tool: Generate Empty TB Environment`           | 当前 Terminal 可提供 cwd           | 在 Terminal cwd 的 `out/sim/` 生成空 TB 环境；完成后可打开 README 或在生成目录打开 Terminal。           |
|                    | `HW Tool: Generate TB From Current Filelist...`    | 当前或 Explorer 选中 `.f`          | 只输入一次 DUT top module，在 filelist 同目录的 `out/sim/` 生成 TB 环境。                               |
| **mem_tool**       | `HW Tool: Open Memory Tool Documentation`          | Python 环境依赖已安装              | 将插件内置的 `mem_tool/README.md` 转换为 HTML，并在 Webview 中打开。                                    |
|                    | `HW Tool: Generate Memory Shell...`                | 当前 Terminal 可提供 cwd           | 只输入一次 subsystem prefix，在 Terminal cwd 的 `out/mem_tool/` 执行 `init` 并打开生成的 shell。        |
|                    | `HW Tool: Integrate Memory From Excel`             | 当前或 Explorer 选中 `.xlsx`       | 输入 SRAM shell prefix，执行 `inst` 并打开集成 PHY instance 后的 memory shell。                         |
| **csr_tool**       | `HW Tool: Open CSR Documentation`                  | Python 环境依赖已安装              | 将插件内置的 `csr_tool/README.md` 转换为 HTML，并在 Webview 中打开。                                    |
|                    | `HW Tool: Create CSR Template...`                  | 已打开 Terminal、文件或工程        | 四选一生成 Markdown/Excel 模板，并可选择是否包含 `base_info`；文件名固定为 `reg_define.md/.xlsx`。      |
|                    | `HW Tool: Create Default CSR Template`             | 已打开 Terminal、文件或工程        | 不弹出选项，直接生成仅包含 `reg_define` 的 `reg_define.md`。                                            |
|                    | `HW Tool: Generate CSR (Single)`                   | 当前文件为 CSR `.md/.xlsx`         | 保存当前输入并生成单模块 CSR，固定输出到输入文件同目录的 `out/`。                                       |
|                    | `HW Tool: Generate CSR (Nested)`                   | 当前文件为 CSR `.md/.xlsx`         | 以 `--nested` 模式生成多层 CSR，固定输出到输入文件同目录的 `out/`；完成后可直接打开 `_tree.html`。      |
|                    | `HW Tool: Open CSR Tree HTML`                      | 当前文件为 CSR `.md/.xlsx`         | 在当前输入对应的 `out/doc/` 中查找 `_tree.html`；存在多个文件时先选择，再使用 Webview 打开。            |
|                    | `HW Tool: Insert CSR Register Row...`              | 当前文件为 CSR Markdown            | 只选择一次 `reg_type`，随后在当前行后插入对应的 `reg_define` 默认行，由用户直接修改表格内容。           |
| **rtl_flist_mgr**  | `HW Tool: Generate RTL Filelist...`                | 当前或 Explorer 选中 `.toml/.core` | 选择 `sim/synth/lint/emu/fpga`，刷新 core 索引并生成到 core 旁的 `out/flist/`。                         |
|                    | `HW Tool: Refresh RTL Core List`                   | 已打开文件、Terminal 或 workspace  | 扫描推断出的 workspace，在 Explorer 的 `RTL Cores` 视图列出本体 core；单击条目打开 corefile。           |
| **git_repo_mgr**   | `HW Tool: Git Repository Status`                   | 当前 Git workspace                 | 在 HW Tool Output 中汇总 top 与 import checkout 的 commit、dirty、missing 状态。                        |
|                    | `HW Tool: Sync Git Repositories...`                | 当前 Git workspace                 | 选择 full/shallow clone 并二次确认后递归同步；已有 checkout 不重复维护。                                |
|                    | `HW Tool: Open Git Dependency Graph...`            | 已执行过 sync                      | 选择只读 tree 或 JSON，在临时编辑器中查看 `.git_repo` 保存的依赖图。                                    |

CSR 模板优先生成到当前激活 Terminal 的工作目录。Terminal 未启用 Shell Integration、无法报告当前目录时，依次回退到当前文件目录和 workspace 根目录。Markdown 生成后在 VS Code 中打开；Excel 生成后使用系统默认的 Office/WPS 打开，以保留数据验证下拉菜单。

## 准备资源

在本仓库根目录执行：

```bash
python -B hw_tool/publish/vscode/scripts/sync_resources.py
```

该步骤会把 `py_rtl_snippet` 的最新 Markdown 片段生成为 `resources/systemverilog.code-snippets`。CSR 模板由插件内置 runtime 调用 `csr_tool template` 动态生成，不再复制整份 `reg_template.md`。

生成插件内置 runtime：

```bash
npm run sync-runtime
```

该步骤复用 `hw_tool/publish/build_release.py`，将 `csr_tool`、`rtl_inst`、`rtl_dummy`、`gen_tb`、`md2html`、`git_repo_mgr`、`rtl_flist_mgr` 与 `mem_tool` 的源码复制到 `runtime/hw_tool/repository/`。`runtime/` 是构建产物，已 Git ignore。

## 系统依赖

插件不内置 Python。安装 `.vsix` 的机器需要 Python 3.11+，并具备 CSR 所需依赖：

```bash
python -m pip install jinja2 openpyxl Markdown
```

默认调用 `python`。若 Python 不在 `PATH`，在 VS Code settings 中配置其绝对路径：

```json
{
  "dmgHwTool.pythonPath": "C:/Python311/python.exe"
}
```

## 调试

在 VS Code 中打开 `hw_tool/publish/vscode/`，按 `F5` 启动 `Run HW Tool VS Code Extension`。新的 Extension Development Host 窗口会加载插件；在该窗口的命令面板中运行 `HW Tool:` 命令。

调试前先执行 `npm run sync-runtime`。Extension Development Host 会使用插件目录的 `runtime/hw_tool/`，因此行为与最终 `.vsix` 一致。

## gen_tb 与 mem_tool

`Generate Empty TB Environment` 和 `Generate Memory Shell...` 严格使用当前激活 Terminal 通过 Shell Integration 报告的 cwd。无法取得 cwd 时会提示先打开 Terminal，不会回退到 workspace 或当前文件目录。

`Generate TB From Current Filelist...` 与 `Integrate Memory From Excel` 均可从当前文件或 Explorer 右键文件调用。`mem_tool inst` 会询问 subsystem prefix：命令行 `-p` 控制 SRAM shell 命名，Excel 的 `prefix` 列继续控制 SRAM wrapper/PHY 的命名与匹配，两者语义独立。

## rtl_flist_mgr 与 git_repo_mgr

`Generate RTL Filelist...` 固定使用绝对路径输出并自动执行 `--rescan`，避免刚修改的 corefile 被旧缓存遮住。生成文件固定为 `<core_dir>/out/flist/<core_name>_<mode>.f`。Explorer 的 `RTL Cores` 视图只展示 workspace 本体 core，符合 CLI `--list-core` 排除 `import/` 的约定。

插件中的 `git_repo_mgr` 是受限入口，只开放 status、sync 和 graph。`sync` 默认推荐完整 clone，也可选择 shallow clone；执行前必须确认。`forall`、`export-flat`、`switch`、`tag` 以及全部 `admin/release` 命令不会注册到 VS Code，仍应在 Terminal 中显式执行。

## 打包

```bash
npm run check
npm run sync-snippets
npm run sync-runtime
npm run package
```

`npm run package` 会自动完成上述三个准备步骤。产物为 `out/dmg-hw-tool-0.4.0.vsix`。安装后，VS Code 会自行管理用户扩展目录；插件约 1 MB，仅依赖系统 Python。打包使用仓库内的 `scripts/pack_vsix.py`，不依赖 `@vscode/vsce` 或网络访问。
