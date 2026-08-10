# AI 工作记录

本文档按时间线记录 `py_tools_for_hw` 的重要设计结论和开发进度，便于后续继续讨论与实现。

## 时间线

### 2026-08-02 至 2026-08-05: `git_repo_mgr` 规划与首版实现

- 每个 node 仅维护直接 Git 依赖 `git_deps.toml`；remote 支持 SSH/HTTPS，单 remote 可省略名称，`ref` 支持 branch、tag 与 commit ID。
- workspace 使用 `top/import/<checkout>/` flat 布局，同一 URL 只保留一份 checkout；ref 冲突、递归循环和 basename 冲突均明确报错。basename 冲突仅允许集成者在 top manifest 通过 `[[checkout]]` 显式命名解决。
- 同步生成 `.git_repo/resolved.toml`、`graph.json`、`tree.txt`；`export-flat` 生成固定 commit 的 `git_deps_flat.toml`，`sync --flat` 用快照恢复集成版本。
- 集成者命令包括 `status`、`switch`、`tag` 与 Google repo 风格的 `forall -c`；`forall` 支持项目筛选、预览、失败汇总和 `REPO_*` 上下文变量。
- 已增加 GitHub/GitLab provider 配置与 `admin` 命令：`policy-status/diff/apply`、`lock-main/unlock-main`、`release/release-resume`、`audit`。策略 token 仅从环境变量读取；lock/release 的原始策略、快照与进度保存于 `.git_repo/admin/`。
- 管理员可用 `protect <branch>` 与 `unprotect <branch>` 批量建立或解除任意分支保护；操作前确认每个 checkout 都存在 `origin/<branch>`，避免仅部分仓库被修改。`policy.branch` 仅作为默认发版分支，默认值为 `main`。
- 已完成独立工具、中文 README 与 9 条临时本地 Git 回归测试。

### 2026-08-06: `rtl_flist_mgr` 设计讨论

- 工具定名 `rtl_flist_mgr`，面向 RTL 工程师维护并生成传统 `.f`；支持新 TOML core、常见 FuseSoC CAPI2 `.core` 与 `legacy_f`，已注册到 `hw_tool_de`。当前版本为 `0.11.0`，固定示例为 `soc -> cpu/npu -> alu_harden/lsu_harden`。
- 与 `git_repo_mgr` 解耦：直接扫描 workspace 本体和 flat `import/*/` checkout，不读取 `.git_repo/resolved.toml`，也不负责 clone。workspace 首次扫描将 core ID、corefile、Git root 与格式缓存到 `.rtl_flist/core_index.toml`；后续默认读缓存，`--rescan` 强制刷新，`--list-core -d` 始终临时扫描。
- 新 TOML 保持最小契约：`[core]` 使用 `id/filesets`，`[fileset.*]` 使用 `dir/files/depend/legacy_f`；不支持 target、when、file_type、include_dirs、defines，也不生成 stub/bbox。历史 `+incdir+`、`+define+`、`-f/-F`、单文件 `-v` 留在 legacy `.f`；外部 DW/SRAM/PDK 优先使用绝对路径。
- 模式白名单为 `sim/synth/lint/emu/fpga`，分别激活 `is_sim/is_synth/is_lint/is_emu/is_fpga`，不提供任意 `--flag`。条件 `condition ? (value)` 仅作用于 fileset 选择、`files` 与 `depend`；未来模式只扩展工具内 `MODE_FLAGS` 映射与回归。
- `first:` 仅可标记 `files` 单项或 `core.filesets` 中的 fileset，使对应内容置于最终 flist 前段；不作用于 `depend/legacy_f`，first fileset 的依赖仍按普通顺序输出。
- 去重按 core ID、真实绝对文件路径、legacy directive 分层执行；不同路径但同 basename 的文件均保留，并给出一次 `W_FILE_NAME_CONFLICT` 告警。`.rtl_flist/core_tree.txt` 保存本次 core 依赖树，`out/` 与 `.rtl_flist/` 为本地生成状态。
