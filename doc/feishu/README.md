# 飞书文档推送

按照仓库根目录 `SUMMARY.md` 的章节顺序和层级，将 Markdown、表格、代码及本地图片推送到飞书知识库。原有 README 不做修改；飞书页面是源码文档的阅读副本。

## 使用

依赖 Python 3.10 以上及 `requests`、`Markdown`（可用 `python -m pip install requests Markdown` 安装）。配置 `FEISHU_APP_ID`、`FEISHU_APP_SECRET` 环境变量；Windows 也支持读取当前用户的环境变量，无须将凭据写入仓库。

在仓库根目录执行：

```powershell
# 预览章节，不联网、不创建页面
python -B doc/feishu/push_summary.py --dry-run

# 推送全部章节；再次运行会跳过未变化的页面
python -B doc/feishu/push_summary.py

# SUMMARY 调整了章节位置、顺序或删减内容时
python -B doc/feishu/push_summary.py --sync-tree
```

默认在已授权的知识库首页下建立 `HW Tool 文档`，保留此前的 CSR 验证页。`SUMMARY.md` 的 `##` 生成分组，列表缩进对应父子文档；章节标题自动添加编号。

指定其他知识库时，为它使用独立的状态文件：

```powershell
python -B doc/feishu/push_summary.py --parent-url https://example.feishu.cn/wiki/NODE_TOKEN --title "项目文档" --state out/feishu_project/state.json
```

应用须已发布文档读写、知识库读写及图片上传权限，并获得目标知识库的编辑权限。

## 更新与状态

`out/feishu_summary/state.json` 保存本地文件与飞书页面的对应关系、内容摘要及文档版本，后续更新必须保留。`cache/` 缓存转换结果；`report.json` 给出入口链接、数量和警告。以上均为本地产物，不包含应用密钥，也不提交到 Git。

内容未变化时跳过；内容变化时更新原页面，链接不变。检测到飞书侧人工编辑则停止，避免覆盖。网络中断且写入结果不明确时也停止，先核对页面和状态再重试，不盲目重复创建。

脚本只管理自己创建的页面，不删除旧章节。`--sync-tree` 按 `SUMMARY.md` 移动并排序原页面，保留页面链接；不再列出的章节移到首页下独立的 `HW Tool 文档 - 历史归档`，不保留在当前目录中。同步前备份本地状态，并检查远端正文是否被人工修改。归档目录也用于排序时临时周转页面；遇到不明确的网络写入结果会停止，需核对状态后继续。

本地文档之间的链接改为对应飞书页面；未导入的源码链接指向 GitHub `main`。跨文档标题锚点降级为页面顶部并给出提示。本地图片自动上传；远端图片暂不下载。凭据、状态文件不要提供给其他人。

## 基础测试

```powershell
python -B -m unittest discover -s doc/feishu -p "test_*.py"
```

`verify_csr.py` 保留为早期单篇 CSR 验证脚本；日常使用 `push_summary.py`。

## 目录保护（2026-09-12）

普通推送会在写入前检查实际知识库、父节点、文档身份、子节点集合与章节顺序，包含历史归档和旧节点。远端缺失、被移到首页、归档失效或出现未登记子页面时停止，不根据本地状态猜测归属。章节删除、移动或在已有章节中间插入需要显式使用 `--sync-tree`；该参数也不能跳过远端状态异常。

`python -B doc/feishu/push_summary.py --check-tree` 只读联网检查，不修改飞书；`--dry-run` 仅预览本地清单。显式章节同步每次移动前检查目标，移动后验证实际父节点，失败保留pending以阻止盲目重试。正文推送前后再次验证完整受管目录。

仅在已授权删除退出清单的页面时使用 `--sync-tree --delete-removed`；它在正文发布成功后由叶子向上删除旧页及临时归档，并记录删除任务与旧页面状态。COMMON RTL 实际推送还需 `--push`。默认不自动删除。

检查不能阻止用户或其他程序在检查后改动飞书；无法将多次远端操作变为原子事务。检测到冲突会停止，已完成的单项移动可能需要核对后恢复。
