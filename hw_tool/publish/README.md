# hw_tool 发布

`publish/` 保存 `hw_tool` 的三种交付入口和离线源码发布脚本。`build_release.py` 将已注册工具复制到单独的 `hw_tool/` 目录，并按发布版本生成 Linux modulefile；发布版本应固定到一个 Git tag 或 commit。

| 发布方式          | 目录               | 交付内容                                          |
| ----------------- | ------------------ | ------------------------------------------------- |
| Windows PATH      | `windows/`         | 用户 PATH 安装脚本与使用说明。                    |
| Linux module load | `linux/`           | Environment Modules/Lmod 使用说明与基础模板。    |
| VS Code           | `vscode/`          | 编辑器扩展源码、资源同步脚本与 `.vsix` 打包配置。 |
| 离线源码包        | `build_release.py` | 生成包含 `repository/` 的独立 `hw_tool/` 目录。   |

从开发源码 checkout 生成离线源码包：

```bash
python -B build_release.py --version 0.1.0
```

开发发布默认使用当前 `py_tools_for_hw` 工作区。正式发布增加 `--official`，并通过 `--repo-ref` 指定 `py_tools_for_hw` 的 tag 或完整 commit，源码从 URL 临时 clone。`--shallow` 可减少所选 ref 的下载历史。

```bash
python -B build_release.py --version 1.1.1 --official \
    --repo-ref py_tools_for_hw=v1.1.1
```

产物位于 `out/hw_tool-0.1.0/hw_tool/`、`out/hw_tool-0.1.0/modulefiles/hw_tool/0.1.0` 与 `out/hw_tool-0.1.0.zip`，可整体复制到 Windows 或 Linux。使用 `--no-archive` 可只生成目录。它不内置 Python runtime；目标环境需安装 Python 3.11+，并安装 `jinja2`、`openpyxl` 和 `Markdown`。生成目录中的 `release_info.toml` 保存发布版本、构建时间和各源码仓库的实际 commit，离开 Git 工作树后 `hw_tool --version` 会使用该信息。`repository/` 和各类 `out/runtime` 产物由 Git ignore，`publish/` 下的脚本、模板和文档纳入 Git。VS Code 扩展会内置同一份工具源码，只依赖系统 Python，不要求 `hw_tool` 位于 PATH。
