# rtl_flist_mgr

## 简介

`rtl_flist_mgr` 扫描 workspace 根目录与 flat 布局的 `import/*/` checkout，递归解析 RTL core TOML 或 legacy FuseSoC `.core`，生成传统 `.f` filelist。它只负责 filelist：不 clone 仓库、不编译 RTL、不生成 stub、不解析 module。

`git_repo_mgr` 可选用于将多 Git 仓库平铺同步到 `import/`，但 `rtl_flist_mgr` 不读取 `.git_repo/resolved.toml`，可在手工准备、解压或其他脚本拉取的 workspace 中独立运行。

`core_id` 推荐采用 `vendor:lib:name`，例如 `dmg:cpu:lsu_harden`：`vendor` 表示组织、`lib` 表示子系统或 IP 分类、`name` 表示稳定 component 名。也兼容 FuseSoC 四段 VLNV `vendor:lib:name:version`，例如 `dmg:cpu:lsu_harden:1.0.0`。它是 filelist 依赖标识，不要求与某个 module 名相同；一个 core 可以包含 package、多个 module 或模型文件。

## 设计初衷

本工具充分借鉴并兼容 FuseSoC `.core` 的 core file、稳定 `core_id`、fileset 和递归依赖思路：每个 IP/子系统在自己的仓库维护直接依赖与文件集合，顶层只引用 core ID，从而将 filelist 去中心化。

新项目更推荐 `.toml + legacy.f`：TOML 负责新的 core/fileset/depend 描述，`legacy.f` 保留传统 filelist 内容。SRAM/DW 仿真模型、PDK 绝对路径、历史仿真选项等不适合强行改造成独立 core 的内容，仍可通过 `legacy_f` 按原有 `rtl_filelist.f` 方式接入。新 TOML 与旧 `.f` 可以逐个 fileset 混用，迁移不必一步完成。

## 常用命令

以下命令在 `rtl_flist_mgr/` 工具目录运行。`src/rtl_flist_mgr.py` 可独立执行，不依赖 Hub；操作其他项目时通过 `-w <workspace>` 指定 root。

```bash
# 初始化 / 查询 root
python -B src/rtl_flist_mgr.py --init-root -w <root>
python -B src/rtl_flist_mgr.py --show-root

# 默认 sim 模式
python -B src/rtl_flist_mgr.py --core <core_id/name> -o <output.f>

# 按完整 core ID 或唯一 name 生成
python -B src/rtl_flist_mgr.py --core dmg:cpu:subsys -w <workspace> -o cpu.f
python -B src/rtl_flist_mgr.py --core subsys -w <workspace> -o cpu.f

# 综合或 lint filelist
python -B src/rtl_flist_mgr.py --core <core_id/name> -m synth -o <output.f>
python -B src/rtl_flist_mgr.py --core <core_id/name> -m lint  -o <output.f>

# 查询当前 workspace 本体 core、显式 workspace 或指定目录 core
python -B src/rtl_flist_mgr.py --list-core
python -B src/rtl_flist_mgr.py --list-core --all
python -B src/rtl_flist_mgr.py --list-core -w <workspace>
python -B src/rtl_flist_mgr.py --list-core -d <directory>
python -B src/rtl_flist_mgr.py --list-core --rescan
python -B src/rtl_flist_mgr.py --help
```

生成 flist 和列出 core 使用同一 root 规则：显式 `-w` 校验目录存在后采用；否则向上查询 `.rtl_flist/workspace.toml`，唯一标记可用，多个祖先标记报歧义。仅有 `.rtl_flist/core_index.toml` 或同目录 `.git` 与 `import/` 并存时只列候选，不自动选中。单独 `.git`、import、空缓存目录及当前目录均不作为兜底。没有明确 root 就报错，不扫描、不生成。

首次显式执行 `python -B src/rtl_flist_mgr.py --init-root -w <root>`，创建内容为 `schema_version = 1` 的 `.rtl_flist/workspace.toml`。普通扫描不会创建标记；`--show-root` 只查询，不扫描也不写缓存，可结合 `-w` 验证指定目录。多个标记时可用 `-w` 消除歧义，不自动删除标记。

`--list-core` 默认仅列 root 本体，排除 `import/`；`--list-core --all` 列出本体与 import 的全部 core。`--all` 仅用于列表且与 `-d` 互斥；`--list-core -d <directory>` 仍仅扫描指定目录。

生成入口仅为 `--core <core_id/name>`，不再接受 corefile 路径位置参数。`--core` 优先精确匹配完整 ID；简写 name 为 ID 第三段，不是 TOML 文件名。兼容四段 ID，多个版本或不同库中 name 相同会列出候选 ID/路径并报错，要求指定完整 ID，不按扫描顺序任选。新增 core 后使用 `--rescan` 更新索引。

输出 `-o` 仍相对当前目录，`-w` 不改变输出位置。上面的 `src/rtl_flist_mgr.py` 写法假设在工具目录执行；在项目任意目录运行时，请使用 `python -B <工具绝对路径>/src/rtl_flist_mgr.py ...`；脚本位置与 workspace root 相互独立。旧命令中的 `soc.toml` 应替换为 `--core dmg:soc:top`，TOML 与 `.core` 的扫描和解析支持不变。

## 常用信息

workspace 命令会在 root 下维护 `.rtl_flist/`。这是工具生成的本地状态目录，应加入 `.gitignore`，不需要人工编辑或提交。

| file                         | purpose                                                                                       |
| ---------------------------- | --------------------------------------------------------------------------------------------- |
| `.rtl_flist/workspace.toml`  | 显式初始化创建的 root 标记；唯一祖先命中时自动采用。                                          |
| `.rtl_flist/core_index.toml` | core 索引缓存，记录 `core_id`、corefile 路径、Git root 与格式；首次扫描或 `--rescan` 时更新。 |
| `.rtl_flist/core_tree.txt`   | 最近一次生成 flist 的已展开 core 依赖树，便于人工核对实际依赖关系；每次成功生成 `.f` 时覆盖。 |

workspace 命令首次执行时扫描 root 与 `import/*/`，将 `core_id`、corefile 路径、Git root 和格式写入 `.rtl_flist/core_index.toml`。之后 `--list-core` 直接读取该索引，不再递归扫描 workspace；生成 `.f` 也按索引定位并解析已登记 corefile。输出中的 `core_index: ... (scan|cache|rescan)` 说明本次来源。

新增、删除、移动 corefile，或修改 `core_id`、`depend` 后，必须显式使用 `--rescan` 刷新缓存。工具不会检查目录时间戳，避免每次调用重新扫描。`--list-core -d <directory>` 是临时目录查询，始终直接扫描且不读写 workspace 缓存。

## Core TOML

```toml
[core]
id = "dmg:cpu:subsys"
filesets = ["rtl", "alu", "!is_synth ? (lsu)"]

[fileset.rtl]
dir = "."
files = ["cpu_subsys.sv"]

[fileset.alu]
dir = "."
files = ["is_synth ? (alu_harden_stub.sv)"]
depend = ["!is_synth ? (dmg:cpu:alu_harden)"]

[fileset.lsu]
depend = ["dmg:cpu:lsu_harden"]
```

| element            | purpose                                                                                             |
| ------------------ | --------------------------------------------------------------------------------------------------- |
| `[core]`           | `id` 是稳定 core 标识；`filesets` 是唯一的 fileset 展开顺序来源。省略时按声明顺序展开全部 fileset。 |
| `[fileset.<name>]` | 一个有序文件集合，只可放 `depend`、`files`、`dir`、`legacy_f`。                                     |
| `depend`           | 有序 core ID 数组。当前 fileset 先递归展开其 `depend`，再输出自己的 `files`。                       |
| `files`            | 相对 dir，dir 不填时相对 TOML 所在目录；解析为绝对路径并检查文件存在。                              |
| `dir`              | 仅允许相对 TOML 所在目录的路径；不填与 . 等价，可写 ../rtl，不允许绝对路径。                        |

## 去重与同名告警

- core 按 `core_id` 去重，同一个 core 只递归展开一次。
- 文件按解析后的真实绝对路径去重，同一文件只在首次出现的位置输出。
- legacy_f 普通 RTL 路径与 TOML files 共同按真实绝对路径去重；-v、+incdir+ 按选项与绝对路径去重，+define+ 按定义内容去重。首次出现的顺序保留。
- 不同路径但 basename 相同的文件不会去重，都会输出；工具在 `stderr` 给出一次 `W_FILE_NAME_CONFLICT` 告警，列出两条冲突路径。

core 依赖环、重复 core_id、TOML files 缺失会报错。允许 ../ 和外部绝对路径，不再按 Git root 限制文件访问；仅处理可信 corefile，不执行 RTL。

## Flist 最前段

`first: ` 可标记单个 `files` 条目，或 `[core].filesets` 中的一个 fileset。被标记内容进入最终 `.f` 的最前段，多个置顶项仍按其原有展开顺序排列；普通文件和所有依赖展开结果随后输出。

```toml
[core]
filesets = ["rtl", "first: prelude"]

[fileset.rtl]
files = ["first: rtl/soc_pkg.sv", "rtl/soc_top.sv"]

[fileset.prelude]
depend = ["dmg:common:pkg"]
files = ["rtl/soc_prelude.sv"]
```

`first:` 不支持 `depend` 或 `legacy_f`。first fileset 中的 `depend` 仍按普通顺序输出，不会因为 fileset 被置顶而改变依赖的输出优先级。条件可组合为 `is_sim ? (first: sim_model)`。

## Flag 与模式

条件写作 `condition ? (value)`，支持 `!`、`&&`、`||`。工具内建互斥 flag：`is_sim`、`is_synth`、`is_lint`、`is_emu`、`is_fpga`。条件可作用于文件、fileset 选择项和 `depend` 中的 core ID 引用；不提供任意 `--flag`，新增 flag 必须在工具的固定模式映射中登记。

| mode    | active flag | typical use                                       |
| ------- | ----------- | ------------------------------------------------- |
| `sim`   | `is_sim`    | 展开 RTL、testbench 和仿真模型。                  |
| `synth` | `is_synth`  | 选择用户维护的 stub，或跳过已 harden 的内部 RTL。 |
| `lint`  | `is_lint`   | 保留待检查 RTL，同时按条件排除 SRAM/DW 仿真模型。 |
| `emu`   | `is_emu`    | 选择仿真加速器专用 RTL、wrapper 或模型。          |
| `fpga`  | `is_fpga`   | 选择 FPGA 专用 RTL、wrapper 或约束关联文件。      |

## 集中管理 Core TOML

TOML 可放在仓库任意位置。可集中到 `<repo>/filelist/`，通过 `dir = ".."` 指向上一级，或 `dir = "../alu"` 指向同级 RTL 子目录。路径只取决于 TOML 所在目录，不取决于 Git、import 布局或执行命令的位置。

```text
cpu/
├── filelist/
│   ├── cpu.toml
│   ├── alu.toml
│   └── lsu.toml
├── cpu_subsys.sv
├── alu/
│   └── alu_harden_top.sv
└── lsu/
    ├── lsu_harden_top.sv
    └── model/
```

这让 core 描述可统一审阅、统一生成和统一检查，同时不会迫使 RTL 目录为 filelist 组织让位。

## Legacy `.f` 与路径

`legacy_f` 指定的 .f 文件相对 TOML 的 dir 定位（dir 不填时相对 TOML）。恢复传统解析：去除注释和空行，递归展开 -f/-F，替换 `$VAR` / `${VAR}`，检查 RTL 和 -v 文件存在，按路径去重，输出规范化绝对路径。legacy_f 仅替换 CLI `--var NAME=VALUE` 提供的变量；未传入的 `$VAR` / `${VAR}` 原样保留，即使同名环境变量存在也不自动展开。含未展开变量的行暂不检查文件存在、不规范化，按替换后的整行文本去重；若是 -f/-F 引用则保留引用，交给后续工具展开。变量全部已知时仍递归展开、按真实路径去重并检查缺失文件和循环引用。沿用原工具规则：-f/-F 的引用及子 .f 内相对路径都以各自所在 .f 目录为基准，不模拟不同仿真器的 cwd 差异。支持 +incdir+、+define+、单文件 -v；-y、+libext+、-work、-L 仍报不支持。建议 DW/SRAM 模型使用真实绝对路径。

TOML、兼容 .core 和变量已全部展开的 legacy_f 文件路径输出规范化绝对路径；legacy_f 允许保留 CLI 未指定的变量占位符及所在行的路径写法。删除 `--path-style`，不再支持 relative/rootvar。新 TOML 不支持 when、include_dirs、defines、file_type，相关传统选项可放进 legacy_f。

## 完整参数

| parameter               | description                                                                                                      |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `--core <core_id/name>` | 生成必填；完整 ID 或唯一第三段 name，不接受 corefile 路径。                                                      |
| `-o <output.f>`         | 生成的 filelist；生成 flist 时必填。                                                                             |
| `-m <mode>`             | 输出模式：`sim`、`synth`、`lint`、`emu` 或 `fpga`；默认 `sim`。                                                  |
| `-w <workspace>`        | 显式 root；否则只自动采用唯一祖先 workspace.toml 标记。                                                          |
| `--show-root`           | 只查询 root 及依据，不扫描、不写文件。                                                                           |
| `--init-root -w <root>` | 显式初始化 workspace 标记，目录须已存在，不扫描 core。                                                           |
| `--var NAME=VALUE`      | `legacy_f` 外部路径变量，可重复指定。                                                                            |
| `--rescan`              | 强制扫描 workspace root 与 `import/*/`，覆盖 `.rtl_flist/core_index.toml`。                                      |
| `--list-core`           | 默认仅列本地 core，排除 import；打印 root_dir 和索引来源。                                                       |
| `--all`                 | 配合 --list-core 列出本地和 import 全部 core，与 -d 互斥。                                                       |
| `-d <directory>`        | 与 `--list-core` 配合，递归列出指定目录下的 core；不解析 depend，也不需要 workspace，并打印该目录为 `root_dir`。 |

## 固定示例与回归

`test/examples/soc_cpu_npu/` 提供 `soc -> cpu/npu` 的完整小型 workspace：CPU 的 core TOML、legacy `.f` 都集中到 `import/cpu/filelist/`，同时覆盖依赖顺序、file/fileset/core-ID 条件、用户维护 stub 与仿真模型。为保证示例 checkout 可直接复用，LSU 的 SRAM 仿真模型由 `legacy_f` 使用 `${SRAM_PATH}` 引入；DW 仿真模型则作为独立 core 依赖引入。实际项目仍推荐将已部署模型写为真实绝对路径。

![soc_cpu_npu architecture](test/examples/soc_cpu_npu/assets/soc_cpu_npu_arch.png)

```bash
python -B test/test_rtl_flist_mgr.py
```

## 使用示例

[固定示例 README](test/examples/soc_cpu_npu/README.md)
