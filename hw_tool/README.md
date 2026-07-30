# hw_tool

`hw_tool` 是公司级工具 hub。它只负责发现和转发各小组的 `hw_tool_<group>`；各小组独立维护自己的注册表、业务工具和测试。

当前已注册 `de` 小组。DE 工具按来源仓库统一注册：同属 `py_tools_for_hw` 的工具共享一个 Git URL 和 checkout，`mem_tool` 使用独立的 `com` Git 仓库。

## 目录结构

```text
hw_tool/
  bin/                  # 公司级 hw_tool 启动器
  src/                  # 公司级 hub
  config/groups.toml    # 小组注册和外部仓库配置
  groups/               # 外部 group 的本地 checkout，默认不提交
  hw_tool_de/           # DE 子 hub，仅包含入口、注册表和测试
    bin/
    src/
csr_tool/               # 保持原业务工具路径
gen_rtl_dummy/
gen_rtl_inst/
py_rtl_sim/
```

## DE 工具来源

`csr_tool`、`rtl_inst`、`rtl_dummy` 和 `gen_tb` 共用 `py_tools_for_hw` Git URL；`mem_tool` 使用 `com` Git URL。`hw_tool de sync --all` 按来源仓库同步，同一仓库只同步一次。

在 `py_tools_for_hw` 源仓库内开发时会优先使用当前工作区，不额外 clone 自身。`hw_tool_de` 独立部署后，父 hub 会传递统一的 `hw_tool/groups/` checkout 根目录；执行 `hw_tool sync --all` 即可拉取各工具来源仓库。

## 使用方式

在 `hw_tool` 目录下直接运行：

```bash
python -B src/hw_tool.py list
python -B src/hw_tool.py help de
python -B src/hw_tool.py de rtl_inst path/to/child.sv
```

Windows 下可将 `hw_tool/bin` 加入 `PATH`。如果只需要当前命令行窗口生效：

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

Linux 下将 `hw_tool/bin` 加入 `PATH` 后使用：

```bash
hw_tool list
hw_tool help de
hw_tool de gen_tb -o sim -top dut_top
```

## 命令

| 命令                    | 说明                                        |
| ----------------------- | ------------------------------------------- |
| `hw_tool list`          | 列出已注册小组 hub 及其可用状态              |
| `hw_tool list --tools`  | 查询全部已就绪 group，列出全局工具索引       |
| `hw_tool help <group>`  | 列出指定小组已注册的工具                     |
| `hw_tool doc <tool>`    | 打印工具当前本地 checkout 中的 README.md     |
| `hw_tool sync <name>`   | clone 或 fast-forward 更新一个 Git group/tool |
| `hw_tool sync --all`    | 更新全部已注册的 Git source                  |
| `hw_tool <group> ...`   | 原样透传参数给指定小组的 `hw_tool_<group>`  |

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
path = "groups/hw_tool_dv"
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

首次同步会 clone 到 `hw_tool/groups/hw_tool_dv/`；后续同步依次执行 `git fetch`、`git checkout <branch>` 与 `git pull --ff-only`。若 checkout 存在未提交修改，`sync` 会拒绝更新，避免覆盖现场改动。外部 checkout 已由 [`.gitignore`](.gitignore) 忽略，不会被提交到公司级 hub 仓库。`hw_tool sync --all` 还会请求每个已就绪 group 同步其内部 Git 工具依赖。

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
