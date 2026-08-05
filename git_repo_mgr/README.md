# git_repo_mgr

`git_repo_mgr` 管理多 Git 仓库的递归依赖与集成版本。每个 node 仅声明直接依赖，工具递归发现完整依赖图；真实 checkout 去重后平铺在 top 的 `import/`，逻辑 tree/DAG 保存在状态文件中。

## 设计初衷

`git_repo_mgr` 借鉴 Google `repo` 的 workspace 操作方式，以及 FuseSoC core dependency 的分布式 tree 思路：开发者维护相邻 node 的依赖，集成者获得 flat checkout、统一状态和可复现版本快照。

| tool                | 优点                                                         | 集成时的限制                                                       |
| ------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------ |
| Google `repo`       | flat workspace，批量拉取仓库、切分支、打 tag 方便            | 集中 manifest 需要维护完整仓库集合；权限隔离和 manifest 编写成本较高 |
| FuseSoC core 依赖   | tree 结构，node 只声明相邻依赖，局部开发和复用较自然          | 跨 node 统一版本、处理版本冲突、批量切分支/打 tag、冻结交付版本较繁琐 |
| `git_repo_mgr`     | 分布式直接依赖声明，递归生成 tree；去重后的 checkout flat 管理 | 首版聚焦 Git workspace 管理，RTL core/fileset 仍由后续 `rtl_filelist` 处理 |

## 命令速览

下文 `<git_repo_mgr>` 表示：

```text
python -B /abs/path/to/git_repo_mgr/src/git_repo_mgr.py
```

在 top Git 仓库内使用：

| command                                               | 用途                                           |
| ----------------------------------------------------- | ---------------------------------------------- |
| `<git_repo_mgr> sync [--shallow]`                    | 递归同步 `git_deps.toml`                       |
| `<git_repo_mgr> sync --flat git_deps_flat.toml`      | 按固定 commit 快照恢复 workspace               |
| `<git_repo_mgr> status`                              | 汇总 top 与 import checkout 状态               |
| `<git_repo_mgr> graph --format tree\|json`           | 查看保存的依赖 tree 或机器可读图                |
| `<git_repo_mgr> export-flat -o git_deps_flat.toml`   | 导出可复现的 flat 快照                         |
| `<git_repo_mgr> switch <branch\|tag\|commit>`       | 统一切换全部 checkout                          |
| `<git_repo_mgr> tag <name> [-m <message>] [--push]`  | 在全部 checkout 创建并可选推送 annotated tag   |
| `<git_repo_mgr> forall -c "<shell command>"`        | 在全部 checkout 中执行 shell 命令               |
| `<git_repo_mgr> admin <command>`                     | 查询或修改远端 main 分支保护与发版状态          |

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

每个 node 仓库根目录只维护自己的直接依赖：

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

## Workspace 与冲突

真实 checkout 仅位于 `top/import/`：

```text
top/
├── import/
│   ├── common_ip/
│   ├── cpu/
│   ├── alu/
│   ├── lsu/
│   ├── npu/
│   └── dma/
└── .git_repo/
```

同一 repository URL 只 checkout 一次；后续依赖关系在 tree 中标记为 `[shared]`。同一 URL 请求不同 `ref`、或递归依赖成环时，同步直接失败并显示完整依赖路径。

默认 checkout 名称为仓库 basename，例如 `common_ip.git` 对应 `import/common_ip/`。不同 URL 出现相同 basename 时，由集成者在 top 的 `git_deps.toml` 显式命名：

```toml
[[checkout]]
repository = "https://github.com/vendor/common_ip.git"
name = "vendor_common_ip"
```

`[[checkout]]` 只影响当前 top workspace；递归子仓库中的同类配置不会覆盖它。

## 状态与版本快照

递归同步成功后自动生成：

```text
.git_repo/resolved.toml    # URL、ref、固定 commit、checkout 路径
.git_repo/graph.json       # 节点和依赖边，供机器读取
.git_repo/tree.txt         # 面向人工的 tree 输出
```

示例 `tree.txt`：

```text
top
├── common_ip
├── cpu
│   ├── common_ip [shared]
│   ├── alu
│   │   └── common_ip [shared]
│   └── lsu
└── npu
    └── dma
```

导出 `git_deps_flat.toml` 后，另一个集成者先取得 top checkout，再执行 `sync --flat`。flat 恢复不递归读取子仓库 manifest，全部仓库以 detached HEAD 固定在快照记录的 commit。

## `forall`

`forall` 对齐 Google `repo forall -c`：按 resolved workspace 顺序在 top 与全部 import checkout 中执行 shell 命令。可在命令末尾给出 checkout 名称筛选范围，`--dry-run` 仅预览，`--fail-fast` 在首次失败后停止。

| environment_variable | description                      |
| -------------------- | -------------------------------- |
| `GIT_REPO_MGR_TOP`  | 当前 top workspace 的绝对路径    |
| `GIT_REPO_MGR_NAME` | 当前 checkout 名称               |
| `GIT_REPO_MGR_PATH` | 当前 checkout 相对 top 的路径    |
| `REPO_PROJECT`      | 当前项目名称                     |
| `REPO_PATH`         | 当前 checkout 相对 top 的路径    |
| `REPO_REMOTE`       | 当前仓库的 repository URL        |
| `REPO_LREV`         | 当前 checkout 的实际 HEAD commit |
| `REPO_RREV`         | resolved 状态中记录的 ref        |

## 管理员策略与发版

日常开发假设所有仓库都使用受保护的 `main`；发版只允许从 `origin/main` 当前提交创建统一 tag。高权限命令通过 GitHub/GitLab 服务端 API 生效，token 不写入仓库文件。

top 根目录创建 `git_repo_admin.toml`：

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

| command                                                 | 用途                                                        |
| ------------------------------------------------------- | ----------------------------------------------------------- |
| `admin policy-status`                                   | 显示各仓库 `main` 的 provider、当前 token 身份与保护状态    |
| `admin policy-diff`                                     | 比较实际策略与 `baseline_mode`，发现人工策略漂移            |
| `admin policy-apply [--dry-run]`                        | 应用日常 baseline 策略                                     |
| `admin lock-main [--mode read-only\|integration-only]` | 保存原始策略后，批量临时锁定 `main`                         |
| `admin unlock-main <lock_id>`                           | 按保存的原始 API 策略精确恢复                               |
| `admin release <tag> [--push]`                          | 校验 clean、受保护 main、`HEAD == origin/main`，保存快照并打 tag |
| `admin release-resume <tag>`                            | 按 release 状态继续未完成 tag/push；main 或 commit 变化时停止 |
| `admin audit`                                           | 输出本地管理员操作审计记录                                   |

示例：

```bash
<git_repo_mgr> admin policy-status
<git_repo_mgr> admin policy-diff
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
