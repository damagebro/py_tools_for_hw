# git_repo_mgr

`git_repo_mgr` 管理多 Git 仓库的递归依赖与集成版本。每个 node 仅声明直接依赖，工具递归发现完整依赖图；真实 checkout 去重后平铺在 workspace_root 的 `import/`，逻辑 tree/DAG 保存在状态文件中。

## 设计初衷

`git_repo_mgr` 借鉴 Google `repo` 的 workspace 操作方式，以及 FuseSoC core dependency 的分布式 tree 思路：开发者维护相邻 node 的依赖，集成者获得 flat checkout、统一状态和可复现版本快照。

| tool              | 优点                                                           | 集成时的限制                                                               |
| ----------------- | -------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Google `repo`     | flat workspace，批量拉取仓库、切分支、打 tag 方便              | 集中 manifest 需要维护完整仓库集合；权限隔离和 manifest 编写成本较高       |
| FuseSoC core 依赖 | tree 结构，node 只声明相邻依赖，局部开发和复用较自然           | 跨 node 统一版本、处理版本冲突、批量切分支/打 tag、冻结交付版本较繁琐      |
| `git_repo_mgr`    | 分布式直接依赖声明，递归生成 tree；去重后的 checkout flat 管理 | 首版聚焦 Git workspace 管理，RTL core/fileset 仍由后续 `rtl_filelist` 处理 |

## 命令速览

下文 `<git_repo_mgr>` 表示：

```text
python -B /abs/path/to/git_repo_mgr/src/git_repo_mgr.py
```

在工作区根目录（`workspace_root`）内使用，既可以是 Git 仓库根目录，也可以是普通本地目录：

| command                                             | 用途                                          |
| --------------------------------------------------- | --------------------------------------------- |
| `<git_repo_mgr> template`                           | 创建 `git_deps.toml`的模板                    |
| `<git_repo_mgr> sync [--shallow]`                   | 递归同步 `git_deps.toml`                      |
| `<git_repo_mgr> sync --flat git_deps_flat.toml`     | 按固定 commit 快照恢复 workspace              |
| `<git_repo_mgr> status`                             | 显示分支、提交、状态汇总及 dirty/missing 明细 |
| `<git_repo_mgr> graph --format tree or json`        | 查看保存的依赖 tree 或机器可读图              |
| `<git_repo_mgr> export-flat -o git_deps_flat.toml`  | 导出可复现的 flat 快照                        |
| `<git_repo_mgr> switch <branch or tag or commit>`   | 统一切换全部 checkout                         |
| `<git_repo_mgr> tag <name> [-m <message>] [--push]` | 在全部 checkout 创建并可选推送 annotated tag  |
| `<git_repo_mgr> forall -c "<shell command>"`        | 在全部 checkout 中执行 shell 命令             |
| `<git_repo_mgr> admin <command>`                    | 查询或修改远端 main 分支保护与发版状态        |

常用示例：

```bash
<git_repo_mgr> sync
<git_repo_mgr> graph --format tree
<git_repo_mgr> forall -c "git status --short"
<git_repo_mgr> forall -c "git log -1 --oneline" cpu alu
<git_repo_mgr> switch main --dry-run
<git_repo_mgr> tag soc_r1p0 -m "SOC R1P0"
```

`switch` 和 `tag` 会先检查全部 checkout 是否 dirty。`tag --push` 在本地全部创建成功后逐仓库推送；Git 不提供多仓库原子提交。

## 依赖声明

在 `git_repo_mgr/` 工具目录直接运行 Python，生成模板，不依赖 Git 仓库或网络：

```bash
# 在当前目录生成；已有同名文件时拒绝覆盖
python -B src/git_repo_mgr.py template

# 在目标项目生成
python -B src/git_repo_mgr.py template -o /project/workspace_root/git_deps.toml
```

模板包含注释形式的 remote/dependency 示例，修改地址并取消注释后生效；未修改时是合法的无依赖清单。`-o` 允许将模板另存为任意文件名，但 `sync` 仍固定读取各仓库根目录的 `git_deps.toml`，并不支持自定义递归清单名称。统一名称使上层只需知道仓库地址和 ref，无需再配置每个子仓库的清单路径；`git_deps_flat.toml` 是另一个独立的版本快照入口，由 `sync --flat <file>` 显式指定。

每个 node 仓库根目录只维护自己的直接依赖：

顶层必须存在 `git_deps.toml`。递归进入子仓库后，没有该文件或文件中没有 dependency 条目（包含空清单、`dependency = []`）时视为 leaf，停止向下递归；该仓库仍保留 checkout 并记录到状态与依赖树，不会生成空清单或修改子仓库。文件存在但 TOML/依赖格式错误、无权限读取、拉取失败或循环依赖仍报错，不作为 leaf 跳过。

```toml
[remote.company]
url = "ssh://git@git.example.com/dmg"

[[dependency]]
repository = "common/common_ip.git"
ref = "main"

[[dependency]]
repository = "https://github.com/vendor/lib_x.git"
ref = "v1.0.0"
```

remote 支持 SSH 和 HTTPS。仅定义一个 remote 时，依赖可省略 `remote`；存在多个 remote 时，相对 `repository` 必须明确填写 `remote`。完整 URL 不填写 `remote`。

`ref` 支持 branch、tag 与 commit ID。工具使用实际解析到的 commit 生成集成快照。

工具会自动归一同一 Git host 上的 SSH、`ssh://`、HTTP 与 HTTPS URL：忽略协议、SSH 用户名、端口、`.git` 和尾部 `/`，按 `host/group/repository` 去重。例如下列 URL 都只会 checkout 一次：

```text
git@git.example.com:dmg/common_ip.git
ssh://git@git.example.com/dmg/common_ip.git
https://git.example.com/dmg/common_ip.git
http://git.example.com/dmg/common_ip/
```

不同 host 不会自动合并，即使仓库路径相同也会视为不同 repository。对于本地路径和 `file://` URL，工具按解析后的真实绝对路径去重。

### 本地替换与强制版本

仅在 workspace_root 的 `[[dependency]]` 配置以下选项；子仓库中的 `local_path`、`force_ref` 不生效。

```toml
[[dependency]]
repository = "https://example.com/project/mid_a.git"
ref = "main"
local_path = "C:/work/mid_a"

# 间接依赖也可在顶层补充声明，覆盖所有引用，不受条目顺序影响。
[[dependency]]
repository = "https://example.com/project/bottom_common.git"
ref = "v2.0.0"
force_ref = true
# local_path = "C:/work/bottom_common"
```

- `local_path` 未填或为空时正常 clone；非空时在 `import/<name>` 创建目录软链接。相对路径基于 workspace_root，目标必须为 Git 仓库根目录，origin 与 repository 归一化后一致。
- 本地允许 dirty、HEAD 与集成版本不同。工具仍从 URL + 有效 ref 获取清单、递归解析子依赖，不读取本地清单或本地 import，不修改链接目标。
- 已有普通 checkout 时拒绝替换，请自行移走并保留需要的内容。同目标软链接复用；不同目标或失效链接报错，不自动删除。Windows 创建软链接需要开发者模式或相应权限。
- `force_ref = true` 使用该条目的 ref 覆盖所有版本请求，并解析覆盖后版本的子依赖；默认 false，版本冲突仍报错。tree/status 显示原请求与最终 ref，兼容性由集成者确认。
- 为保护调试仓库，包含本地链接时暂不支持批量 switch/tag/admin、flat 导出或恢复；`forall` 选中链接时也报错，可按名称仅选择普通 checkout。删除 `local_path` 后，需手动移除链接再 sync，工具不会沿链接 clone 或 checkout。

两项可独立或组合使用：`force_ref` 决定集成版本和依赖来源，`local_path` 只替换源码位置。它们不自动消除目录重名或循环依赖。

## Workspace 与冲突

### 定位 workspace

- 指定 `--workspace <directory>`（简写 `-w`）：直接使用该目录，要求已存在，不改用父 Git 仓库。
- 省略 `--workspace`：从当前目录向上查找 `.git_repo/resolved.toml`；没有状态文件时，再查找 `git_deps.toml`。每一级规则都要求唯一命中，多处命中或全部未命中时报错，需显式指定 `--workspace`。
- 状态文件优先于子仓库清单，因此同步后可在 `workspace_root/import/cpu/rtl/` 等子目录执行命令。

`show-root` 显示定位目录和依据；`sync` 开始时也显示 root。常规同步要求 root 下存在 `git_deps.toml`；`template` 不查找 workspace，默认在当前目录创建模板。

```bash
# 在项目任意子目录执行，替换下面的工具脚本路径
python -B /path/to/git_repo_mgr/src/git_repo_mgr.py show-root
python -B /path/to/git_repo_mgr/src/git_repo_mgr.py sync

# 显式指定 workspace，也可指定普通目录
python -B /path/to/git_repo_mgr/src/git_repo_mgr.py sync --workspace /project/workspace_root
python -B /path/to/git_repo_mgr/src/git_repo_mgr.py status -w /project/workspace_root
```

### Workspace 根目录与 import

所有依赖仓库统一放到 `workspace_root/import/<checkout_name>/`，管理状态保存在 `workspace_root/.git_repo/`。

- **workspace_root 是 Git 仓库**：workspace_root 与 import 仓库一起参与 Git 操作；workspace_root 需要 origin 和有效提交。
- **workspace_root 是普通目录**：无需 `git init`，支持 sync、status、graph、export-flat、switch、tag、forall；Git 操作仅作用于 import，不操作 workspace_root 或其父 Git 仓库。
- workspace_root 的 Git 身份发生变化后，先重新 sync。普通 workspace_root 的 flat 快照只固定依赖版本，本地配置需自行保存；admin 发布/保护命令仍要求 Git workspace。

### 去重与冲突

- **同一仓库**：按归一化 URL 去重，只保留一份 checkout，重复依赖在 tree 中标记为 `[shared]`。
- **版本冲突或循环依赖**：同步失败，并显示冲突/循环的依赖路径，不自动选择版本。
- **目录重名**：默认使用仓库 basename；不同仓库同名时，在 workspace_root 的 `git_deps.toml` 显式指定 checkout 名称：

```toml
[[checkout]]
repository = "https://github.com/vendor/common_ip.git"
name = "vendor_common_ip"
```

该仓库将落到 `workspace_root/import/vendor_common_ip/`。命名配置以当前 workspace_root 为准，子仓库中的同类配置不会覆盖它。

## 状态与版本快照

递归同步成功后自动生成：

```text
.git_repo/resolved.toml    # URL、ref、固定 commit、checkout 路径
.git_repo/graph.json       # 节点和依赖边，供机器读取
.git_repo/tree.txt         # 面向人工的 tree 输出
```

示例 `tree.txt`：

```text
workspace_root
├── common_ip
├── cpu
│   ├── common_ip [shared]
│   ├── alu
│   │   └── common_ip [shared]
│   └── lsu
└── npu
    └── dma
```

导出 `git_deps_flat.toml` 后，另一个集成者先取得 workspace_root checkout，再执行 `sync --flat`。flat 恢复不递归读取子仓库 manifest，全部仓库以 detached HEAD 固定在快照记录的 commit。

## `forall`

`forall` 对齐 Google `repo forall -c`：按 resolved workspace 顺序在 workspace_root 与全部 import checkout 中执行 shell 命令。可在命令末尾给出 checkout 名称筛选范围，`--dry-run` 仅预览，`--fail-fast` 在首次失败后停止。

| environment_variable | description                              |
| -------------------- | ---------------------------------------- |
| `GIT_REPO_MGR_TOP`   | 工作区根目录的绝对路径（保留原变量名）   |
| `GIT_REPO_MGR_NAME`  | 当前 checkout 名称                       |
| `GIT_REPO_MGR_PATH`  | 当前 checkout 相对 workspace_root 的路径 |
| `REPO_PROJECT`       | 当前项目名称                             |
| `REPO_PATH`          | 当前 checkout 相对 workspace_root 的路径 |
| `REPO_REMOTE`        | 当前仓库的 repository URL                |
| `REPO_LREV`          | 当前 checkout 的实际 HEAD commit         |
| `REPO_RREV`          | resolved 状态中记录的 ref                |

## 管理员策略与发版

`policy.branch` 是发版使用的默认受保护分支，默认为 `main`；发版只允许从该分支的 `origin/<branch>` 当前提交创建统一 tag。完成全仓统一切换后，管理员也可显式保护或解除任意分支。高权限命令通过 GitHub/GitLab 服务端 API 生效，token 不写入仓库文件。

workspace_root 根目录创建 `git_repo_admin.toml`：

```toml
[policy]
branch = "main"
baseline_mode = "integration-only"

[[provider]]
name = "github"
type = "github"
host = "github.com"
api_url = "https://api.github.com"
token_env = "GITHUB_TOKEN"
github_users = ["release-bot"]
github_teams = ["release"]

[[provider]]
name = "gitlab"
type = "gitlab"
host = "gitlab.example.com"
api_url = "https://gitlab.example.com/api/v4"
token_env = "GITLAB_TOKEN"
gitlab_allowed_to_push = [{ user_id = 1001 }]
gitlab_allowed_to_merge = [{ user_id = 1001 }]
gitlab_allowed_to_unprotect = [{ access_level = 40 }]
```

`integration-only` 只允许配置中的 release 用户、团队或 app 修改 `main`；GitLab 必须显式给出 `gitlab_allowed_to_push`。`read-only` 则禁止全部直接 push/merge，适合短时冻结。无 token 或 API 权限不足时，管理员命令直接失败。

| command                                                         | 用途                                                                    |
| --------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `admin policy-status`                                           | 显示各仓库默认分支的 provider、当前 token 身份与保护状态                |
| `admin policy-diff`                                             | 比较默认分支实际策略与 `baseline_mode`，发现人工策略漂移                |
| `admin policy-apply [--dry-run]`                                | 对默认分支应用日常 baseline 策略                                        |
| `admin protect <branch> [--mode read-only or integration-only]` | 先确认全部 `origin/<branch>` 存在，再批量建立指定分支保护               |
| `admin unprotect <branch>`                                      | 先确认全部 `origin/<branch>` 存在，再批量删除指定分支保护               |
| `admin lock-main [--mode read-only or integration-only]`        | 保存原始策略后，批量临时锁定默认分支                                    |
| `admin unlock-main <lock_id>`                                   | 按保存的原始 API 策略精确恢复                                           |
| `admin release <tag> [--push]`                                  | 校验 clean、受保护默认分支、`HEAD == origin/<branch>`，保存快照并打 tag |
| `admin release-resume <tag>`                                    | 按 release 状态继续未完成 tag/push；默认分支或 commit 变化时停止        |
| `admin audit`                                                   | 输出本地管理员操作审计记录                                              |

示例：

```bash
<git_repo_mgr> admin policy-status
<git_repo_mgr> admin policy-diff
<git_repo_mgr> switch integration_r1
<git_repo_mgr> admin protect integration_r1
<git_repo_mgr> admin unprotect integration_r1
<git_repo_mgr> admin lock-main --mode read-only
<git_repo_mgr> admin unlock-main main-20260805T120000Z
<git_repo_mgr> admin release soc_r1p0 --push
<git_repo_mgr> admin release-resume soc_r1p0
```

管理员状态保存在未提交的 `.git_repo/admin/`：`locks/<lock_id>.json` 保存恢复用的原始策略，`releases/<tag>.json` 和同名 `.toml` 保存 release 进度与固定版本快照，`audit.jsonl` 保存操作审计。多仓库 API 和 tag push 不具备原子事务；`release-resume` 只继续缺失步骤，绝不移动已有 tag 或强推。

## 回归测试

```bash
python -B test/test_git_repo_mgr.py
```

测试使用临时本地 Git 仓库，不访问网络，覆盖递归去重、tree/flat 输出、ref 冲突、循环依赖、checkout 名称冲突、flat 恢复、批量 tag、`forall` 和管理员策略/release 状态机。
