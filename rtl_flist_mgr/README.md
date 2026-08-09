# rtl_flist_mgr

## 简介

`rtl_flist_mgr` 扫描 workspace 根目录与 flat 布局的 `import/*/` checkout，递归解析 RTL core TOML 或 legacy FuseSoC `.core`，生成传统 `.f` filelist。它只负责 filelist：不 clone 仓库、不编译 RTL、不生成 stub、不解析 module。

`git_repo_mgr` 可选用于将多 Git 仓库平铺同步到 `import/`，但 `rtl_flist_mgr` 不读取 `.git_repo/resolved.toml`，可在手工准备、解压或其他脚本拉取的 workspace 中独立运行。

`core_id` 推荐采用 `vendor:lib:name`，例如 `dmg:cpu:lsu_harden`：`vendor` 表示组织、`lib` 表示子系统或 IP 分类、`name` 表示稳定 component 名。也兼容 FuseSoC 四段 VLNV `vendor:lib:name:version`，例如 `dmg:cpu:lsu_harden:1.0.0`。它是 filelist 依赖标识，不要求与某个 module 名相同；一个 core 可以包含 package、多个 module 或模型文件。

## 设计初衷

本工具充分借鉴并兼容 FuseSoC `.core` 的 core file、稳定 `core_id`、fileset 和递归依赖思路：每个 IP/子系统在自己的仓库维护直接依赖与文件集合，顶层只引用 core ID，从而将 filelist 去中心化。

新项目更推荐 `.toml + legacy.f`：TOML 负责新的 core/fileset/depend 描述，`legacy.f` 保留传统 filelist 内容。SRAM/DW 仿真模型、PDK 绝对路径、历史仿真选项等不适合强行改造成独立 core 的内容，仍可通过 `legacy_f` 按原有 `rtl_filelist.f` 方式接入。新 TOML 与旧 `.f` 可以逐个 fileset 混用，迁移不必一步完成。

## 常用命令

```bash
# 默认 sim 模式
python -B src/rtl_flist_mgr.py <core_file> -o <output.f>

# 综合或 lint filelist
python -B src/rtl_flist_mgr.py <core_file> -m synth -o <output.f>
python -B src/rtl_flist_mgr.py <core_file> -m lint  -o <output.f>

# 查询当前 workspace 本体 core、显式 workspace 或指定目录 core
python -B src/rtl_flist_mgr.py --list-core
python -B src/rtl_flist_mgr.py --list-core -w <workspace>
python -B src/rtl_flist_mgr.py --list-core -d <directory>
python -B src/rtl_flist_mgr.py --help
```

生成 flist 时，`-w <workspace>` 默认当前目录。`--list-core` 未传 `-w` 时会从当前目录向上寻找 workspace root：优先最近含 `.rtl_flist/` 的目录，其次最近含 `import/` 的目录；两者均不存在时，以当前目录为 root。每次 `--list-core` 都先打印 `root_dir: <path> (<source>)`，便于确认本次推断结果。默认查询仅列 root 本体 core，排除 `import/`。

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

| element            | purpose |
| ------------------ | ------- |
| `[core]`           | `id` 是稳定 core 标识；`filesets` 是唯一的 fileset 展开顺序来源。省略时按声明顺序展开全部 fileset。 |
| `[fileset.<name>]` | 一个有序文件集合，可放 `depend`、`files`、`dir`、`include_dirs`、`defines`、`legacy_f`、`file_type`。 |
| `depend`           | 有序 core ID 数组。当前 fileset 先递归展开其 `depend`，再输出自己的 `files`。 |
| `files`            | 有序文件数组；文件相对 `dir`，未填 `dir` 时相对 TOML 所在目录。 |
| `dir`              | 相对所属 Git root，适合将多个 core TOML 集中到 `filelist/` 而 RTL 保持原目录。 |

同一个 core 或文件被多处引用时，只在第一次出现的位置展开/输出；依赖环、重复 `core_id`、缺失文件和路径逃出 Git root 都会报错。

## Flag 与模式

条件写作 `condition ? (value)`，支持 `!`、`&&`、`||`。工具内建互斥 flag：`is_sim`、`is_synth`、`is_lint`。条件可作用于文件、fileset 选择项和 `depend` 中的 core ID 引用。

| mode    | active flag | typical use |
| ------- | ----------- | ----------- |
| `sim`   | `is_sim`    | 展开 RTL、testbench 和仿真模型。 |
| `synth` | `is_synth`  | 选择用户维护的 stub，或跳过已 harden 的内部 RTL。 |
| `lint`  | `is_lint`   | 保留待检查 RTL，同时按条件排除 SRAM/DW 仿真模型。 |

## 集中管理 Core TOML

TOML 可放在仓库任意位置。推荐在复杂子系统中集中到 `<repo>/filelist/`，让 RTL、模型和 wrapper 保持原目录，使用 fileset 的 `dir` 指向 Git root 下的实际位置：

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

`legacy_f` 可在 TOML fileset 中封装旧 `.f`，支持普通文件、`-f` / `-F`、`+incdir+`、`+define+`。外部目录由 `--var NAME=VALUE` 显式传入；未支持的 legacy 选项会报错。常见 FuseSoC CAPI2 `.core`、fileset `depend` 与 `targets.default` 也保持兼容。

默认 `--path-style absolute`，适合后端、DW/SRAM 等绝对模型目录；也可选择 `relative` 或 `rootvar`。

## 完整参数

| parameter               | description |
| ----------------------- | ----------- |
| `core_file`             | 顶层 core TOML 或 `.core`；生成 flist 时必填。 |
| `-o <output.f>`         | 生成的 filelist；生成 flist 时必填。 |
| `-m <sim|synth|lint>`   | 输出模式，默认 `sim`。 |
| `-w <workspace>`        | workspace 根目录；`import/*/` 自动视为独立 checkout root。生成 flist 时默认当前目录。 |
| `--path-style`          | `absolute`、`relative` 或 `rootvar`，默认 `absolute`。 |
| `--var NAME=VALUE`      | `legacy_f` 外部路径变量，可重复指定。 |
| `--list-core`           | 列出 workspace 本体 core，排除 `import/`；未传 `-w` 时优先通过 `.rtl_flist/`、其次 `import/` 向上推断 workspace root，并打印 `root_dir`。 |
| `-d <directory>`        | 与 `--list-core` 配合，递归列出指定目录下的 core；不解析 depend，也不需要 workspace，并打印该目录为 `root_dir`。 |

## 固定示例与回归

`test/examples/soc_cpu_npu/` 提供 `soc -> cpu/npu` 的完整小型 workspace：CPU 的 core TOML 集中到 `import/cpu/filelist/`，同时覆盖依赖顺序、file/fileset/core-ID 条件、用户维护 stub 与仿真模型。

![soc_cpu_npu architecture](test/examples/soc_cpu_npu/assets/soc_cpu_npu_arch.png)

```bash
python -B test/test_rtl_flist_mgr.py
```

## 使用示例

`rtl_flist_mgr\test\examples\soc_cpu_npu\README.md`

