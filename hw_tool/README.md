# hw_tool

## 联邦 Hub

`hw_tool` 是可独立运行的 hub，也可以作为另一个 `hw_tool` 的 group 被注册。父 hub 不复制或二次维护子 hub 的业务工具；它只调用子 hub 的 `list --recursive --json`，取得带路由的工具清单后完成展示与命令转发。

每个可集成 hub 需要保持以下稳定接口：`list --recursive --json`、`run <qualified_tool>`、`help`、`doc`、`sync`、`doctor`、`verify`、`test` 和 `--version`。递归清单使用 schema version `1`，每个工具包含 `name`、`qualified_name`、`route`、`status`、`description`、`doc_url` 字段。

```bash
hw_tool list --recursive
hw_tool list --recursive --json
hw_tool run de.csr_tool -i register.md --nested -o out
hw_tool de.csr_tool -i register.md --nested -o out
hw_tool help de.csr_tool
hw_tool doc de.csr_tool
```

`qualified_name` 以 group 路径连接，例如 `de.csr_tool`，更深层的集成可形成 `soc.de.csr_tool`。未冲突的短名仍可直接调用；出现重名时请使用限定名。父 hub 在启动子 hub 时传递访问链，若发现 `A -> B -> A` 形式的循环集成会立即报错，避免递归发现或同步无限循环。

外部仓库把本仓库的 `hw_tool` 作为 group 注册时，入口应指向 `src/hw_tool.py`，并由自身的 `groups.toml` 定义本地 checkout 路径：

```toml
[group.de_tools]
source = "git"
path = "repository/py_tools_for_hw/hw_tool"
entry = "src/hw_tool.py"
description = "Hardware development tool federation."
repository = "https://github.com/damagebro/py_tools_for_hw.git"
branch = "main"
```

随后执行 `hw_tool sync de_tools` 拉取该 hub；`hw_tool sync --all` 会继续请求所有已就绪子 hub 同步自己的依赖。`--shallow` 可用于首次浅克隆。

## 工具注册契约

业务工具可以使用任意语言和内部目录结构；注册到 group 时，只需要提供一个可执行入口、帮助和稳定返回码。成功返回 `0`，参数或用法错误返回 `2`，业务执行失败返回 `1`。`--version` 是可选能力；未实现时不影响注册或验证。

下面以 `example_tool` 为例：

```python
import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate example output.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(f"write: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

```python
ToolSpec(
    name="example_tool",
    script="example_tool/src/main.py",
    description="Generate example output.",
    usage="hw_tool de example_tool --output <path>",
    readme="example_tool/README.md",
    doc_url="https://git.example.com/de/example_tool/README.md",
    repository_name="de_tools",
    example="example_tool/test/input.txt",
    smoke_args=("--input", "{example}", "--output", "{output}/result.txt"),
    smoke_outputs=("result.txt",),
    unit_tests=("example_tool/test/test_main.py",),
    unit_cwd="example_tool",
)
```

业务工具应保持目录内独立运行，不依赖仓库根目录的公共 Python 模块。group 如需复用代码，可在自己的仓库或工具目录内维护。

`hw_tool` 是公司级工具 hub。它只负责发现和转发各小组的 `hw_tool_<group>`；各小组独立维护自己的注册表、业务工具和测试。

当前已注册 `de` 小组。DE 工具按来源仓库统一注册：同属 `py_tools_for_hw` 的工具共享一个 Git URL 和 checkout，`mem_tool` 使用独立的 `com` Git 仓库。

## 目录结构

```text
hw_tool/
  bin/                  # 公司级 hw_tool 启动器
  src/                  # 公司级 hub
  config/groups.toml    # 小组注册和外部仓库配置
  repository/           # 业务工具与外部 group 的本地 checkout，默认不提交
  publish/              # Windows、Linux、VS Code 三种发布入口
    windows/            # PATH 安装脚本
    linux/              # modulefile 模板
    vscode/             # VS Code 扩展源码和 .vsix 打包配置
  hw_tool_de/           # DE 子 hub，仅包含入口、注册表和测试
    bin/
    src/
```

## DE 工具来源

`csr_tool`、`rtl_inst`、`rtl_dummy` 和 `gen_tb` 共用 `py_tools_for_hw` Git URL；`mem_tool` 使用 `com` Git URL。`hw_tool de sync --all` 按来源仓库同步，同一仓库只同步一次。

在 `py_tools_for_hw` 源仓库内开发时会优先使用当前工作区，不额外 clone 自身。`hw_tool_de` 独立部署后，父 hub 会传递统一的 `hw_tool/repository/` checkout 根目录；执行 `hw_tool sync --all` 即可拉取各工具来源仓库。

## 使用方式

在 `hw_tool` 目录下直接运行：

```bash
python -B src/hw_tool.py list
python -B src/hw_tool.py --version
python -B src/hw_tool.py doctor
python -B src/hw_tool.py help de
python -B src/hw_tool.py de rtl_inst path/to/child.sv
```

## 发布方式

`hw_tool` 的发布产物可独立为一个目录：发布脚本将已注册工具源码复制到 `repository/`，运行时不再依赖外层 `py_tools_for_hw/`。源码发布保持跨平台；目标机器需提供兼容的 Python 与工具依赖。发布版本推荐固定到 Git tag 或 commit；通过 `hw_tool --version` 可核对实际 tag/commit。

完整操作见 [hw_tool_release_guide.md](hw_tool_release_guide.md)，发布目录总览见 [publish/README.md](publish/README.md)。Windows PATH、Linux module load 与 VS Code 分别由 `publish/windows/`、`publish/linux/`、`publish/vscode/` 维护。

### Windows PATH

Windows 下将 `<py_tools_for_hw>/hw_tool/bin` 加入用户 `PATH`。如果只需要当前命令行窗口生效：

```bat
cd /d path\to\py_tools_for_hw
set "PATH=%CD%\hw_tool\bin;%PATH%"
```

如果需要写入当前用户的永久 `PATH`，在 PowerShell 中执行：

```powershell
cd path\to\py_tools_for_hw
$bin = (Resolve-Path .\hw_tool\bin).Path
$old = [Environment]::GetEnvironmentVariable("Path", "User")
if (($old -split ";") -notcontains $bin) {
    [Environment]::SetEnvironmentVariable("Path", "$bin;$old", "User")
}
```

重新打开终端后使用：

```bat
hw_tool.cmd list
hw_tool.cmd de csr_tool -i register.md --nested -o out
```

### Linux module load

管理员按版本保留 `build_release.py` 生成的独立源码目录，例如：

```text
/tools/hw_tool/
└── 0.1.0/
    └── hw_tool/
        ├── bin/
        ├── repository/
        └── ...
```

开发构建默认使用当前 `py_tools_for_hw` 工作区和 `com@main`。正式构建通过 `--official` 为两个仓库分别指定 tag 或完整 commit，两边都从 URL clone，不使用当前工作区内容。以下命令同时生成源码目录和版本化 modulefile：

```bash
python3 -B hw_tool/publish/build_release.py --version 0.1.0 --official \
    --repo-ref py_tools_for_hw=v0.1.0 --repo-ref com=v1.2.0 --no-archive
sudo mkdir -p /tools/hw_tool/0.1.0 /tools/modulefiles/hw_tool
sudo cp -a hw_tool/publish/out/hw_tool-0.1.0/hw_tool /tools/hw_tool/0.1.0/
sudo cp hw_tool/publish/out/hw_tool-0.1.0/modulefiles/hw_tool/0.1.0 /tools/modulefiles/hw_tool/0.1.0
```

生成的 `/tools/modulefiles/hw_tool/0.1.0` 内容如下，版本由 `--version` 自动写入，不需要 `sed`：

```tcl
#%Module
module-whatis "Hardware development tool hub 0.1.0"

set root /tools/hw_tool/0.1.0/hw_tool
prepend-path PATH $root/bin
setenv HW_TOOL_HOME $root
setenv HW_TOOL_VERSION 0.1.0
```

系统管理员可将 `/tools/modulefiles` 加入全局 `MODULEPATH`；用户也可临时执行：

```bash
module use /tools/modulefiles
module load hw_tool/0.1.0
hw_tool --version
hw_tool list
hw_tool help de
hw_tool de gen_tb -o sim -top dut_top
module unload hw_tool/0.1.0
```

该 Tcl modulefile 同时兼容 Environment Modules 与 Lmod；卸载时会自动恢复 `PATH`、`HW_TOOL_HOME` 和 `HW_TOOL_VERSION`。发布机需具备 Python 3、Git 以及各工具要求的 Python 依赖。

## 命令

| 命令                              | 说明                                              |
| --------------------------------- | ------------------------------------------------- |
| `hw_tool --version`               | 显示当前 hub 的 Git tag/commit、提交日期时间与 dirty 状态 |
| `hw_tool doctor`                  | 检查 Python、Git、PATH、注册项、依赖和子 group 状态 |
| `hw_tool verify [group\|--all]`   | 快速检查各 group 的工具契约与注册完整性          |
| `hw_tool test --all`              | 发布前汇总执行各 group 的完整回归                |
| `hw_tool list`                    | 列出已注册小组 hub 及其可用状态                    |
| `hw_tool list --tools`            | 查询全部已就绪 group，列出全局工具索引             |
| `hw_tool help <group>`            | 列出指定小组已注册的工具                           |
| `hw_tool doc <tool>`              | 打印工具当前本地 checkout 中的 README.md           |
| `hw_tool sync <name> [options]`   | 预览或更新一个 Git group/tool                      |
| `hw_tool sync --all [options]`    | 预览或更新全部已注册的 Git source                  |
| `hw_tool <group> ...`             | 原样透传参数给指定小组的 `hw_tool_<group>`        |

`--version` 使用 `git describe --tags --always --dirty` 和最新 commit 日期时间（精确到分钟）；当前没有 tag 时显示 commit ID，有本地修改时追加 `-dirty`。离线发布包不在 Git 工作树内时，改为读取 `release_info.toml` 中的版本和构建时间。`doctor` 中的 `[warn] launcher` 表示当前终端尚未从更新后的 `PATH` 启动，不影响通过 `python -B src/hw_tool.py` 调用。

## 契约与回归

顶层 `hw_tool` 不重复运行各工具的业务回归。它通过 `verify` 请求每个 group 自检契约；完整单元测试和最小样例生成由各 group 自己维护并执行。

```bash
hw_tool verify
hw_tool de verify
hw_tool de test --unit
hw_tool de test --smoke csr_tool
hw_tool de test --all
hw_tool test --all
```

`hw_tool test --all` 仅建议在发布前使用；日常提交由各 group 的 CI 执行自己的 `test --all`。

同步前可先预览，不会创建目录，也不会执行 clone、fetch、checkout 或 pull：

```bash
hw_tool sync --all --dry-run
hw_tool de sync csr_tool --dry-run
```

默认首次同步会 clone 指定分支的完整历史。增加 `--shallow` 时，缺失 checkout 会使用 `git clone --depth 1`；已有 checkout 不会被改写或截断：

```bash
hw_tool sync --all --shallow
hw_tool de sync mem_tool --shallow
```

`hw_tool <group> help <tool>` 会显示该工具的参数帮助和已注册的 `document:` URL。例如：

```bash
hw_tool de help csr_tool
```

完整文档可直接输出到终端：

```bash
hw_tool doc csr_tool
hw_tool de doc mem_tool --all
hw_tool doc csr_tool --from 49
```

`doc` 默认输出 48 行，并提示继续阅读命令；`--all` 输出完整 README，`--from <line>` 从指定行继续。每个 group 在自己的 `ToolSpec` 中维护 `readme` 相对路径与可选 `doc_url`。`doc` 使用本地 README，`help` 显示浏览器文档 URL。

## 省略 Group

`hub.default_group` 当前配置为 `de`。当工具名全局唯一时，group 名可省略：

```bash
hw_tool mem_tool --help
hw_tool csr_tool -i register.md --nested -o out
```

顶层会调用每个已就绪 group 的 `list --json`，临时建立工具索引，不在顶层重复维护工具清单。解析规则如下：

| 工具归属情况                  | 省略 group 时的行为                              |
| ----------------------------- | ----------------------------------------------- |
| 仅一个 group 提供该工具       | 自动转发到该 group                              |
| 多个 group 提供且默认组提供   | 自动转发到默认 group                            |
| 多个 group 提供且默认组不提供 | 报错并列出候选；使用显式 `hw_tool <group> <tool>` |

显式 group 调用始终有效：

```bash
hw_tool de csr_tool -i register.md --nested -o out
hw_tool dv run_case smoke
```

## 外部 Git Group

顶层 group 配置位于 [groups.toml](config/groups.toml)。当前 `de` 是本地 group；DV、SOC、SW 等独立仓库可按文件中的注释模板增加：

```toml
[group.dv]
source = "git"
path = "repository/hw_tool_dv"
entry = "src/hw_tool_dv.py"
description = "Design verification tools."
doc_url = "https://company.example/hw_tool_dv/README.md"
repository = "ssh://git@company.example/hw_tool_dv.git"
branch = "main"
```

配置完成后执行：

```bash
hw_tool sync dv
hw_tool dv list
hw_tool sync --all
```

首次同步会 clone 到 `hw_tool/repository/hw_tool_dv/`；后续同步依次执行 `git fetch`、`git checkout <branch>` 与 `git pull --ff-only`。若 checkout 存在未提交修改，`sync` 会拒绝更新，避免覆盖现场改动。外部 checkout 已由 [`.gitignore`](.gitignore) 忽略，不会被提交到公司级 hub 仓库。`hw_tool sync --all` 还会请求每个已就绪 group 同步其内部 Git 工具依赖。

## 嵌套规则

顶层注册项由 `groups.toml` 生成，均使用 `kind="hub"` 并指定 `tool_home`。父 hub 启动子 hub 时会显式设置子进程的 `HW_TOOL_HOME`，使每个小组的注册表都可使用相对本小组目录的脚本路径。

```toml
[group.de]
source = "local"
path = "hw_tool_de"
entry = "src/hw_tool_de.py"
description = "Digital engineering tools."
```

新增小组时维护其自己的 `hw_tool_<group>` 仓库与注册表，再在 [groups.toml](config/groups.toml) 增加本地或 Git group 配置。
