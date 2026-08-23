# hw_tool 发布

`publish/` 保存 `hw_tool` 的三种交付入口和离线源码发布脚本。`build_release.py` 将已注册工具复制到单独的 `hw_tool/` 目录；发布版本应固定到一个 Git tag 或 commit。

| 发布方式          | 目录               | 交付内容                                          |
| ----------------- | ------------------ | ------------------------------------------------- |
| Windows PATH      | `windows/`         | 用户 PATH 安装脚本与使用说明。                    |
| Linux module load | `linux/`           | Environment Modules/Lmod modulefile 模板。        |
| VS Code           | `vscode/`          | 编辑器扩展源码、资源同步脚本与 `.vsix` 打包配置。 |
| 离线源码包        | `build_release.py` | 生成包含 `repository/` 的独立 `hw_tool/` 目录。   |

从开发源码 checkout 生成离线源码包：

```bash
python -B build_release.py --version 0.1.0
```

产物位于 `out/hw_tool-0.1.0/hw_tool/` 与 `out/hw_tool-0.1.0.zip`，可整体复制到 Windows 或 Linux。使用 `--no-archive` 可只生成目录。它不内置 Python runtime；目标环境需安装 Python 3.11+，并安装 `csr_tool` 所需的 `jinja2`、`openpyxl`。生成目录中的 `release_info.toml` 保存版本与构建时间，离开 Git 工作树后 `hw_tool --version` 会使用该信息。`repository/` 和 `out/` 都由 Git ignore。VS Code 扩展调用已发布到 PATH 的 `hw_tool`；它只提供编辑器交互，不复制 Python 工具的业务实现。
