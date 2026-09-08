# GitBook 维护与接入

## 文档来源

GitBook 通过仓库根目录的 [.gitbook.yaml](../.gitbook.yaml) 读取 [README.md](../README.md) 作为首页，通过 [SUMMARY.md](../SUMMARY.md) 组织导航。每一页直接使用原目录的 Markdown 文件，现有 README 不复制、不移动。完整章节方案见 [实施计划](plan_gitboot.md)。

## 首次接入

1. 将 `.gitbook.yaml`、`SUMMARY.md` 和新增说明文档提交到要同步的分支。仓库首页 `README.md` 也必须已纳入 Git。
2. 在 GitBook 中创建或选择文档 Space，启用 GitHub/GitLab Git Sync，授权访问本仓库。
3. 选择仓库和分支，Project directory 使用仓库根目录，不选择 `doc/` 或某个工具目录。
4. 首次同步选择从 Git 仓库导入内容，确认目录来自 `SUMMARY.md`。
5. 在 GitBook 预览中检查目录、代码块、图片、表格和跨页链接，确认后按项目需要发布站点。

本配置本身不会创建 GitBook 账号、提交代码、推送分支或发布站点。GitBook 的界面选项可能随版本更新，以当前 Git Sync 页面为准。

## 日常维护

工具正文继续维护对应 README；新增章节时，只在 `SUMMARY.md` 添加仓库根目录相对路径。子章节在父条目下缩进，同一文件只收录一次。图片和正文中的相对链接仍以所在 Markdown 文件的位置为基准。

Git Sync 支持双向同步。为保持仓库正文管理方式，建议在 Git 仓库中编辑 README，通过提交和同步更新 GitBook；在 GitBook 编辑正文也可能产生仓库内容变更。

生成目录 `out/`、插件 `runtime/`、仓库缓存 `repository/`、测试临时目录和历史工作记录不加入导航。不启用自动扫描目录，以免将生成副本或内部计划变成用户手册章节。

## 本地检查

在仓库根目录运行以下命令，检查目录目标文件和重复引用。它只做本地路径检查，不代表已完成云端渲染验收。

```bash
python -B -c "from pathlib import Path; import re; p=Path('SUMMARY.md'); links=re.findall(r'\]\(([^)]+)\)', p.read_text(encoding='utf-8')); missing=[x for x in links if not Path(x).is_file()]; assert not missing, missing; assert len(links)==len(set(links)), 'duplicate pages'; print(f'OK: {len(links)} pages')"
```

## 线上验收

重点检查 CSR 定义中的复杂表格、RTL/Shell 代码块、各工具图片、SoC 示例树以及相对链接。指向未收录 Markdown、源码、Excel 或生成文件的链接不一定能作为 GitBook 页面访问，需在实际同步后检查；生成文件应先按工具说明生成。

当前交付的是 GitBook 文档源与导航配置，不是离线 HTML 站点。若后续需要公司内网静态站点或离线阅读，可单独增加构建方案，并继续复用这些 README。

## 官方说明

- [内容配置](https://gitbook.com/docs/getting-started/git-sync/content-configuration)
- [Git Sync 问题排查](https://gitbook.com/docs/getting-started/git-sync/troubleshooting)
