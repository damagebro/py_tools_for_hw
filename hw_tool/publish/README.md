# hw_tool 发布

`publish/` 保存三种发布方式的源码与模板，`release.py` 是统一发布入口。一个命令生成 Windows/Linux 共用源码 ZIP、版本化 modulefile 和内置相同 runtime 的 VSIX。目标机仍需 Python 3.11+，不需要联网获取工具源码。

以下命令在 `py_tools_for_hw` 仓库根目录执行：

```bash
# 开发发布：使用当前工作区，包括未提交修改
python -B hw_tool/publish/release.py --version 1.1.1-dev.1

# 正式发布：只从注册 URL 获取指定 tag，也支持完整 40 位 commit
python -B hw_tool/publish/release.py --version 1.1.1 --official \
    --repo-ref py_tools_for_hw=v1.1.1

# 校验交付目录，或解压后的 hw_tool 目录
python -B hw_tool/publish/verify_release.py hw_tool/publish/out/hw_tool-1.1.1
```

版本使用 `MAJOR.MINOR.PATCH` 或带预发布后缀的形式，例如 `1.1.1-dev.1`，不接受 `+build`。VSIX 的 `package.json` 仅在暂存副本中更新，源工作区版本不被修改。正式发布的插件、Snippet 定义和 Python 工具全部来自同一次 clone，不混用当前工作区。

```text
out/hw_tool-1.1.1/
├── hw_tool/                      # 独立源码，含 repository/、tool_docs.json
│   ├── release_info.toml          # version/time/URL/ref/commit/tag/branch/dirty
│   └── SHA256SUMS                # 包内文件校验
├── modulefiles/hw_tool/1.1.1
├── hw_tool-1.1.1.zip
├── dmg-hw-tool-1.1.1.vsix
└── SHA256SUMS                    # 整个交付目录及 ZIP/VSIX 校验
```

| 选项                   | 说明                                                       |
| ---------------------- | ---------------------------------------------------------- |
| `--version`            | 必填，统一所有产物版本。                                   |
| `--official`           | 从 URL clone；必须指定 tag 或完整 commit，不接受 branch。   |
| `--repo-ref NAME=REF`   | 当前来源为 `py_tools_for_hw`，其中已包含 `mem_tool`。        |
| `--shallow`            | 正式构建仅 fetch 所选 ref 的浅层历史。                      |
| `--output-root`        | 输出根目录，默认 `hw_tool/publish/out`。                    |
| `--linux-install-root` | Linux 安装根目录，默认 `/tools/hw_tool`，必须是绝对路径。    |

同版本输出已存在时直接失败，不提供自动覆盖；请使用新版本或新输出根目录。构建使用同一磁盘的临时目录和版本锁，校验通过才重命名为最终目录。失败不会留下最终发布目录，也不会删除旧发布物；进程被强制终止时可能留下隐藏暂存目录和 `.hw_tool-<version>.lock`，确认没有构建进程后再人工清理。

校验会检查文件增删、SHA256、必要工具入口、Git metadata、ZIP/VSIX runtime 一致性及 Linux 启动器执行位和 LF。`__pycache__` 和 `.pyc` 是运行期缓存，不在清单内。SHA256 用于发现内容变化，不能防止同时修改文件与清单；防恶意篡改需要只读制品库或签名。

`build_release.py` 保留为底层源码构建 helper；`vscode/scripts/` 保留插件开发辅助流程，正式交付统一使用 `release.py`。打包只需 Python；JS 回归另需 Node.js。`linux/test_release.sh` 用于实际 Linux/WSL 验收，不会自动 push、打 tag 或修改全局 PATH。

`publish/` 下脚本、模板和文档纳入 Git；`out/`、插件 `runtime/`、`node_modules/` 和 `.vsix` 产物忽略。部署方法和 WSL 命令见 [三种发布方式操作指南](../hw_tool_release_guide.md)。
