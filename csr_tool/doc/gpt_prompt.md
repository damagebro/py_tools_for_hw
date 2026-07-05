# CSR Tool Rebuild Prompt

## 1. 使用方式

将本文完整提供给一个具备文件读写和命令执行能力的 GPT coding agent，并让它在
`csr_tool/` 目录内工作。目标不是解释设计，而是重新实现并验证一套可运行的 CSR
自动生成工具。

开始编码前必须同时阅读以下文件：

1. `csr_tool/README.md`
2. `csr_tool/doc/reg_template.md`
3. `com/doc/coding_style.md`
4. `csr_tool/input/*.md`

本文记录的是当前可运行版本的实现契约。若上述文档存在草稿、规划或 TBD，以本文
明确描述的已实现行为为准；RTL 排版和命名始终以 `coding_style.md` 为最高优先级。

---

## 2. 给 GPT 的任务

你是一名熟悉 Python、SystemVerilog、UVM RAL 和固件寄存器定义的高级工程师。
请从规范重新开发 `csr_tool`，不要保留空函数或仅打印占位内容。

工具必须：

- 使用 Python 3.10+。
- 支持 Markdown、XLSX、JSON 三种输入。
- 支持 single 和 nested 两种模式。
- 生成 Markdown、HTML、XLSX 和条件式 JSON 文档。
- 为 nested 树中的每个唯一模块生成 CSR RTL、typedef、wrapper 和集成模板。
- 为每个唯一模块生成自检 Testbench 和 UVM RAL package。
- 在 nested 模式生成 Firmware C Header。
- 不依赖 pandas。
- Markdown 基础流程只依赖 Python 标准库。
- XLSX 使用 `openpyxl`；未安装时给出清晰提示。
- 所有人工写入和生成的文本文件使用 UTF-8、LF 换行。
- 所有生成 RTL 必须符合 `com/doc/coding_style.md`。

不要修改用户无关文件，不要提交生成目录 `out/`。

---

## 3. 目标目录结构

```text
csr_tool/
├── README.md
├── requirements.txt
├── test_parser.py
├── doc/
│   ├── gpt_prompt.md
│   └── reg_template.md
├── input/
│   ├── top_reg.md
│   ├── mid_a_reg.md
│   ├── mid_b_reg.md
│   ├── leaf_a1_reg.md
│   ├── leaf_a2_reg.md
│   ├── json/
│   │   └── convert_md2json.py
│   └── xlsx/
│       └── convert_md2xlsx.py
└── src/
    ├── __init__.py
    ├── autogen_reg.py
    ├── models.py
    ├── reg_common.py
    ├── reg_parser.py
    ├── reg_gen_doc.py
    ├── reg_gen_rtl.py
    ├── reg_gen_tb.py
    └── reg_gen_firmware.py
```

依赖文件：

```text
jinja2>=3.1,<4
openpyxl>=3.1,<4
```

当前 HTML 生成可以直接使用标准库，不强制使用 Jinja2。

仓库 `.gitignore` 至少忽略：

```gitignore
csr_tool/out/
csr_tool/input/xlsx/*.xlsx
csr_tool/input/json/*.json
```

---

## 4. 中间数据模型

在 `src/models.py` 使用 dataclass。后续所有生成器只依赖模型，不重新解析原始文件。

### 4.1 BaseInfoModel

字段：

```python
reg_bitwidth: int = 32
system_baseaddr: int = 0
system_bytesize: int | None = None
system_prefix: str = ""
author: str = ""
email: str = ""
extras: dict[str, str]
```

### 4.2 SpecialOptions

字段：

```python
repeat: int = 1
shadow: int = 0
bytesize: int | None = None
slv_filename: str = ""
extras: list[str]
```

要求：

- `has_shadow` 属性表示 `shadow > 0`。
- `to_text()` 按以下顺序输出：
  `slv_filename`、`bytesize`、`repeat`、`shadow`、`extras`。
- 无特殊属性时返回 `-`。
- `bytesize` 使用大写十六进制，例如 `bytesize=0x400`。
- `shadow 1` 格式化为 `shadow`。

### 4.3 FieldModel

字段：

```python
name: str
msb: int
lsb: int
sw_access: str
default_values: list[int]
description: str
```

提供：

- `width = msb - lsb + 1`
- `default_value`：将默认值格式化为逗号分隔的十六进制字符串。
- `default_for(index)`：索引超过列表时沿用最后一个值。

### 4.4 RegisterModel

字段：

```python
name: str               # 去重后的名字
raw_name: str           # 用户填写的名字
offset: int             # 模块内相对地址，禁止存绝对地址
reg_type: str
sw_access: str
special: SpecialOptions
description: str
fields: list[FieldModel]
source_row: int
```

提供：

- `repeat` 属性。
- `byte_size(word_bytes)`。
- `default_word(index)`：将所有 field 默认值按 bit 位置拼成寄存器默认值。

### 4.5 SubModuleNode

字段：

```python
instance_name: str
offset: int
bytesize: int
source_path: str
module_obj: ModuleModel
```

### 4.6 ModuleModel

字段：

```python
name: str
source_path: str
base_info: BaseInfoModel
registers: list[RegisterModel]
sub_modules: list[SubModuleNode]
```

提供：

- `word_bytes = reg_bitwidth // 8`
- `local_size`：模块内所有寄存器或地址区域占用的最大结束地址。
- `walk()`：深度优先遍历，返回 `(module, absolute_base, path_tuple)`。
- 根绝对地址从 `system_baseaddr` 开始，子节点绝对地址为父基址加子节点 offset。
- `to_dict()`：输出可序列化字典。
- `clean_name(path)`：文件名转小写，并移除 `_reg` 或 `_register` 后缀。

保留兼容别名：

```python
BaseInfo = BaseInfoModel
SubModuleInstance = SubModuleNode
```

---

## 5. 公共函数

在 `src/reg_common.py` 实现：

- `CSRValidationError(ValueError)`
- `parse_int`
- `parse_optional_int`
- `parse_special`
- `validate_identifier`
- `expand_defaults`
- `clog2`
- `hex_width`
- `write_text`
- `write_json`

整数支持：

- Python `int`
- 整数型 float
- 十进制
- `0x` 十六进制
- 数字中的下划线，例如 `0xf000_0000`

标识符必须符合 `[A-Za-z_][A-Za-z0-9_]*`，统一转小写。检查 Python、C、
SystemVerilog 和 VHDL 保留字；VHDL 列表覆盖 VHDL-2008 以及常用
VHDL-2019 PSL 相关保留字。错误信息必须指出用户可见的模块、寄存器或字段。

`expand_defaults` 行为：

- 空值视为 0。
- CSV 值用于 `repeat N`。
- 少于 N 时沿用最后一个值。
- 多于 N 报错。
- 默认值超出 field 位宽报错。

---

## 6. 输入解析

主类：

```python
CSRParser(input_path: str, nested: bool = False)
module = parser.parse()
```

### 6.1 Markdown

识别：

- `# base_info`，可选。
- `# reg_define`，必选。
- Markdown 表格对齐行必须忽略。
- UTF-8 BOM 必须兼容。

### 6.2 XLSX

- 必须有 `reg_define` sheet。
- 可选 `base_info` sheet。
- 第一行为列名。
- 空行忽略。
- 没有 `openpyxl` 时抛出清晰的 ImportError。

### 6.3 JSON

接受：

- 顶层直接是 module 字典。
- 或 `{"module": {...}}`。
- `base_info` 为对象。
- 寄存器列表可叫 `reg_define` 或 `registers`。
- 支持生成器 `ModuleModel.to_dict()` 输出的结构化 registers/fields/special。
- 也支持接近原表格的一行一个 field 格式。

### 6.4 base_info

识别别名：

```text
system_addr      -> system_baseaddr
system_base_addr -> system_baseaddr
system_size      -> system_bytesize
system_byte_size -> system_bytesize
```

`reg_bitwidth` 必须在 8 到 64 之间并且按 byte 对齐。

### 6.5 reg_define 列

以下列全部必须存在，列名大小写只对 `SW_access` 做兼容处理：

```text
offset
reg_name
field
msb
lsb
SW_access
default_value
reg_type
special
description
```

### 6.6 新寄存器和 field continuation

- 行中 `offset` 或 `reg_name` 任一非空，表示新寄存器。
- 新寄存器必须填写 `reg_name`。
- `offset` 和 `reg_name` 都为空但 field 非空，表示上一寄存器的下一个 field。
- 第一条寄存器前不能出现 continuation。
- 空 offset 自动使用上一地址区域结束地址。

### 6.7 reg_name 去重

先统计所有新寄存器的原始名字：

- 只出现一次：保持原名。
- 出现多次：全部编号为 `name1`、`name2`、`name3`。

编号后的名字用于 RTL、文档、TB 和 Firmware。

### 6.8 reg_type 与 SW_access

严格绑定：

```text
cfg     -> RW
status  -> RO
cmd     -> W1T
toggle  -> W1T，并在模型中归一化为 cmd
irq     -> W1C
slave   -> 空
mem     -> 空
```

用户填写非空但不匹配时必须报错。

### 6.9 special

逗号分隔，支持：

```text
repeat N
shadow
shadow N
bytesize=0x...
slv_filename=xxx.md
```

约束：

- `repeat >= 1`
- `shadow` 只允许 cfg。
- `slave` 必须填写 `slv_filename`。
- 非 slave 禁止 `slv_filename`。
- `mem` 必须填写 `bytesize`。
- 非 slave/mem 禁止 `bytesize`。
- slave/mem 不支持 repeat。
- 未识别 special 必须报错，不要静默忽略。
- 同一模块所有 `shadow N` 且 `N >= 2` 的 N 必须一致。
- `shadow`/`shadow 1` 可以与 `shadow N >= 2` 共存。

### 6.10 地址检查

- offset 必须按 `word_bytes` 对齐。
- 手填 offset 必须大于等于前一个地址区域结束地址。
- `repeat N` 占 `N * word_bytes`。
- slave/mem 占 `bytesize`。
- 地址重叠必须打印当前和前一个寄存器信息。
- 模块 `local_size` 不得超过父节点分配的 bytesize。
- 若模块同时有 `system_bytesize` 和父分配 bytesize，使用较小值。

slave 未填写 bytesize 时：

- 若后面还有寄存器，推导为下一寄存器 offset 减当前 offset。
- 若是最后一项且有 `system_bytesize`，推导为 system_bytesize 减当前 offset。
- 其他情况报错。

### 6.11 field 检查

- 非 slave/mem 至少有一个 field。
- slave/mem 禁止 field。
- `0 <= lsb <= msb < reg_bitwidth`
- 同一寄存器 field 位段不能重叠。
- 同一寄存器 field 名不能重复。
- continuation 行的非空 SW_access 必须与寄存器一致。

### 6.12 nested

- 只在 nested 模式递归加载 slave。
- 子文件路径相对于父输入文件目录。
- 子文件不存在时报错。
- 使用 active path stack 检查递归引用环。
- 同一源模块可以在树中实例化多次。

最重要的内部约束：所有 `RegisterModel.offset` 始终是模块内相对地址，绝对地址仅由
`ModuleModel.walk()` 计算。

---

## 7. CLI

入口为 `src/autogen_reg.py`，既支持直接脚本运行，也支持 package import。

参数：

```text
-i, --input     必填，.md/.xlsx/.json
-o, --outdir    默认 out
-m, --mode      single 或 nested，默认 single
--nested        --mode nested 的兼容别名
```

Python API：

```python
run(input_path: str, outdir: str, nested: bool) -> list[Path]
```

执行顺序：

1. parse
2. doc
3. RTL
4. TB/RAL
5. firmware

用户输入错误只打印 `[ERROR] ...` 并返回 1，不默认打印 traceback。成功打印：

```text
[OK] Generated N files in <absolute output path>
```

---

## 8. 文档生成

类：

```python
DocGenerator(module, out_dir)
generate_all(is_nested=False) -> list[Path]
```

### 8.1 Single

生成：

```text
out/doc/<block>_gen.md
out/doc/<block>_gen.xlsx
out/doc/<block>_gen.json   # 仅当输入本身为 JSON
```

Markdown 输出必须可以再次作为输入，并得到相同模型和生成结果。格式化后的表格：

- base_info 包含 bitwidth、base address、可选 size/prefix/author/email/extras。
- reg_define 第一条 field 行填写寄存器属性。
- 后续 field 行将 offset、reg_name、SW_access、reg_type、special 留空。
- slave/mem 单独输出一行。

### 8.2 Nested

对树中每个节点生成 `<block>_gen.md`，并生成：

```text
<root>_tree.md
<root>_tree.html
<root>_tree.xlsx
<root>_tree.json   # 仅当根输入为 JSON
```

tree Markdown 包含：

- Address Map 表三列为 `block`、`address_range`、`bytesize`。
- block 内容使用树形编号加当前 block name，例如 `1 top`、`1.1 mid_a`，
  不输出 `top/mid_a` 完整路径。
- 按深度优先顺序列出每个模块的寄存器表。
- block 标题下面直接输出寄存器表，不输出 Base address 或 Source 条目。
- tree Markdown 寄存器表第一列叫 `address`，使用绝对地址。
- 绝对地址为 system_baseaddr 加各层 slave offset，再加当前寄存器 offset。
- single 的 `<block>_gen.md` 仍使用相对 `offset`，保持可回灌。

tree HTML：

- 单文件离线 HTML。
- Address Map 第一列为 block，内容使用树形编号和当前 block name，可跳转。
- 每个模块使用 `<details>` 折叠。
- 页面使用左侧导航栏和右侧正文的双栏布局。
- 侧边栏包含 Address Map、模块路径和模块内寄存器链接。
- 侧边栏默认折叠为 52px，只显示 hamburger 展开按钮。
- 点击按钮展开为 280px，再次点击收起；按钮同步更新 aria-label/title。
- 每个模块标题使用原生 `<details>/<summary>`，默认收起。
- 点击模块标题可独立展开或折叠该模块的寄存器链接。
- summary 只负责折叠，不能在 summary 内嵌覆盖点击区域的链接。
- 展开内容只显示寄存器链接，不显示 Overview。
- 桌面端侧边栏 sticky、占满视口高度并独立滚动。
- 窄屏时侧边栏变为顶部横向导航，并隐藏二级寄存器链接。
- 所有导航链接必须指向真实存在的 address/module/register id。
- 寄存器导航显示绝对地址，例如 `top_ctrl (0xF0000000)`。
- 每张 register table 上方有独立标题：
  `<reg_name> (0x<absolute_address>)`。
- register table 内部的 reg_name 单元格只显示名字，不重复显示括号地址。
- 模块标题使用树形章节编号，只显示当前 block name：
  `1 top`、`1.1 mid_a`、`1.1.1 leaf_a1`，不显示完整路径。
- tree 中同名 block 出现多次时，所有实例按深度优先顺序唯一化为
  `<block>_u1`、`<block>_u2`；该名字用于 Address Map、侧栏、block 标题
  和 XLSX sheet 名，但不修改 RTL module 名或单模块文件名。
- HTML block 标题只显示树形编号和当前 block name，不附加 base/source。
- 每个寄存器使用一张独立的 `register-table`。
- 寄存器属性区依次显示：
  - `reg_name` 与绝对 `address`
  - `reg_type` 与 `special`
  - 合并后的 `SW_access`，不分别显示 SW/HW
- field 区使用当前输入规范的表头：
  `field`、`bit_scope`、`default_value`、`description`。
- `bit_scope` 合并输入中的 msb/lsb，显示为 `[msb:lsb]`，例如 `[31:0]`。
- Markdown/XLSX/JSON 输入输出模型仍分别保留 msb 和 lsb，不做 schema 修改。
- 不照搬参考页面中的中文表头或 `type/spec/default/comment` 别名。
- 属性表头和 field 表头使用灰色背景，值单元格使用白色背景。
- register table 不使用 `width: 100%` 铺满页面。
- `field`、`bit_scope`、`default_value` 三列各宽 `20ch`。
- `description` 列宽 `60ch`，整张 register table 宽 `120ch`。
- 页面较窄时由模块 `<details>` 提供横向滚动。
- 不依赖外部 CSS/JS。

tree XLSX：

- 第一张 sheet 为 `address_map`。
- Address Map 使用 `address_range`，格式为
  `0x<start_addr> ~ 0x<end_addr>`。
- Address Map 数据列为 `block`、`address_range`、`bytesize`，不显示 source。
- block 使用树形编号和当前 block name，不使用完整路径。
- `bytesize` 使用十六进制，例如 `0x800`。
- HTML Address Map 不铺满正文，三列各宽 `30ch`，整表宽 `90ch`。
- 根节点范围使用 `system_bytesize`，子节点范围使用父节点分配的 bytesize。
- 后续每个节点一张 sheet。
- 每个 block sheet 第一列为 `address`，内容是逐级累加后的绝对地址。
- address_map 有跳转到对应 sheet 的 hyperlink。
- sheet 名最长 31 字符并去重。
- 第一行加粗和填色，freeze panes，auto filter，自动列宽。

---

## 9. RTL 生成

接口：

```python
generate_rtl(module, out_dir) -> list[Path]
```

对 `module.walk()` 中每个唯一 `source_path` 生成一次：

```text
out/rtl/<block>.sv
out/rtl/plus/<block>_typedef.sv
out/rtl/plus/<block>_wrap.sv
out/rtl/plus/tmp_<block>.sv
```

同一模块在树中实例化多次时不能重复覆盖为不同内容。

### 9.1 主模块参数与 bus

```systemverilog
parameter CSR_AW = 32
parameter CSR_DW = <reg_bitwidth>
```

parameter 声明不添加 `integer` 类型。

端口：

```systemverilog
input  wire                  clk
input  wire                  rst_n
input  wire                  i_csr_req_write
input  wire [CSR_AW-1:0]     i_csr_req_addr
input  wire [CSR_DW-1:0]     i_csr_req_wdata
input  wire [CSR_DW/8-1:0]   i_csr_req_wstrb
input  wire                  i_csr_req_valid
output reg                   o_csr_req_ready
output wire [CSR_DW-1:0]     o_csr_rsp_rdata
output wire                  o_csr_rsp_rvalid
```

写请求没有 response；读请求通过 rvalid/rdata 返回。

主 RTL 与 wrapper 的端口顺序固定为：

1. `clk/rst_n/clear`
2. CSR RX：上游 request 与 read response
3. CSR TX：发往 slave/mem 的 request/response 数组
4. CSR register：cfg/status/cmd/irq
5. shadow 控制、debug 和 error

CSR RX/TX 必须连续放在一起，所有 CSR register 相关端口放在最后。

`clear` 为高有效同步清零：

- 端口顺序位于 `clk/rst_n` 之后。
- 不加入 always sensitivity list。
- 时序逻辑必须先使用 `if (!rst_n)`，再使用 `else if (clear)`。
  禁止合并写成 `if (!rst_n || clear)`；因此 rst_n 异步、clear 同步且优先级明确。
- clear 恢复 cfg/cmd/shadow 默认值，并清空 local response、outstanding
  counter 和 shadow FIFO 控制状态。
- clear 有效时 `o_csr_req_ready=0`、TX request valid=0、RX response valid=0。

### 9.2 field 端口

```text
cfg:
  o_cfg_<reg>_<field>

status:
  i_sta_<reg>_<field>

cmd:
  o_cmd_<reg>_<field>

irq:
  i_irqsta_<reg>_<field>
  o_irqclr_<reg>_<field>
```

repeat 使用 packed array：

```systemverilog
output wire [N-1:0][FIELD_W-1:0] o_cfg_xxx
```

位宽和 repeat 都为 1 时不写 range。

### 9.3 端口排版

这是强制验收项。所有主模块和 wrapper 端口必须统一计算全端口最大列宽，将以下内容
排成五列：

1. direction
2. `wire`/`reg`
3. packed range 或 typedef
4. signal name
5. comma

示例：

```systemverilog
    input  wire                     i_csr_req_write      ,
    input  wire [CSR_AW-1:0]        i_csr_req_addr       ,
    output wire [1:0][CSR_DW-1:0]   o_tx_csr_req_wdata   ,
    input  wire [1:0]               i_tx_csr_rsp_rvalid  //,
```

- 普通端口与 slv 数组端口必须共享同一列宽。
- 所有逗号位于同一列。
- 所有 signal name 起始于同一列。
- 最后一个端口不用真实逗号，在同一列输出 `//,`。
- 每行只声明一个端口。

### 9.4 本地寄存器行为

`cfg`：

- DFF 在生成模块内部。
- 软件 RW。
- reset 使用 field 默认值。
- 写入使用对应 field 的 `i_csr_req_wdata & w_csr_wmask`，不与旧值合并。

`status`：

- DFF 在 user RTL。
- CSR 只采样输入并提供软件读取。

`cmd`：

- DFF 在生成模块内部。
- W1T：写数据 bit 为 1 且 byte strobe 有效时翻转。
- 软件可读回当前 toggle 值。

`irq`：

- 状态 DFF 在 user RTL。
- 软件读取 `i_irqsta_*`。
- W1C 写入组合地产生 `o_irqclr_*`，没有内部 IRQ 状态 DFF。

本地读译码组合块开头统一执行 `w_local_rdata = '0;`，随后使用
`case (i_csr_req_addr)`。每个 `REG_<NAME>_ADDR` case item 只覆盖对应 field，
确保有效寄存器的保留位为 0；`default` 对未命中的本地空洞地址返回
`CSR_INVALID_RDATA`。

```systemverilog
localparam [CSR_DW-1:0] CSR_INVALID_RDATA = CSR_DW'(32'hDEAFDEAF);
```

`w_local_rdata` 的空洞地址分支与 `w_rsp_rdata` 的默认分支必须共同使用
`CSR_INVALID_RDATA`。

response mux 的 `case (r_read_slv)` 每个分支和 `default` 都必须完整赋值
`w_rsp_rdata/w_rsp_rvalid`，case 前不重复添加默认赋值。

每个 cfg/cmd RegisterModel 使用一个独立 `always @(posedge clk or negedge rst_n)`。
本地写握手条件必须抽为：

```systemverilog
assign b_req_fire = i_csr_req_valid && o_csr_req_ready;
assign b_read_fire = b_req_fire && !i_csr_req_write;
assign b_rsp_fire = w_rsp_rvalid;
assign b_local_read_fire = b_read_fire && (w_req_slv == SLV_LOCAL);
assign b_local_write_fire = b_req_fire && i_csr_req_write &&
                            (w_req_slv == SLV_LOCAL);
```

所有握手成功事件统一使用 `_fire` 后缀，不生成 `_accept` 信号。
cfg/cmd 写译码和 IRQ clear 统一使用 `b_local_write_fire`，地址条件与其写在
同一个 `if` 或组合表达式中，避免重复展开 request、write 和 slv 条件。

### 9.5 byte strobe

组合生成 `w_csr_wmask`：

```systemverilog
for (int byte_idx = 0; byte_idx < CSR_DW / 8; byte_idx = byte_idx + 1)
    w_csr_wmask[byte_idx*8 +: 8] = {8{i_csr_req_wstrb[byte_idx]}};
```

`byte_idx` 只在 for 初始化语句中声明，不单独生成 `integer byte_idx;`。

cfg 写公式：

```text
storage <= wdata & mask
```

cmd 写公式：

```text
old ^ (wdata & mask)
```

### 9.6 shadow 1

- 增加全模块端口 `i_pulse_shadow_upen`。
- 软件写 `r_shd_<reg>_<field>`。
- 软件读和 user RTL 输出看到 working `r_<reg>_<field>`。
- upen 时 shadow 提交到 working。
- reset 时 shadow 和 working 都使用默认值。

### 9.7 shadow N，N >= 2

所有深 shadow 共用 FIFO 控制：

```text
i_pulse_shadow_upen
i_pulse_shadow_rden
o_dbg_shadow_wr_idx
o_dbg_shadow_rd_idx
o_dbg_shadow_water_level
o_pulse_err_write_when_full
o_pulse_err_read_when_empty
```

实现：

- 一份 shadow 数据。
- N 份 working 数据。
- push 将 shadow 写到 `working[wr_idx]`。
- pop 推进 `rd_idx`。
- count 支持同周期 push/pop。
- 指针到 N-1 后回零，不能假设 N 是 2 的幂。
- water level = N - count，空时 N，满时 0。
- 满 push 和空 pop 错误输出为组合逻辑。
- user RTL 输出和软件读使用 `working[rd_idx]`。
- `shadow 1` 与深 shadow 共用 upen，但各自更新自己的 working。

### 9.8 slave/mem slv bus

每个 slave/mem 占一个固定 packed array 索引。若 slv 数为 M，端口为：

```text
o_tx_csr_req_write[M]
o_tx_csr_req_addr[M][CSR_AW]
o_tx_csr_req_wdata[M][CSR_DW]
o_tx_csr_req_wstrb[M][CSR_DW/8]
o_tx_csr_req_valid[M]
i_tx_csr_req_ready[M]
i_tx_csr_rsp_rdata[M][CSR_DW]
i_tx_csr_rsp_rvalid[M]
```

slv 地址输出减去该区域起始 offset，转换为 slv 本地地址。

每个 slave/mem slv 必须生成包含末地址的范围 localparam：

```systemverilog
localparam [CSR_AW-1:0] SLV_<BLOCK_NAME>_ADDR_S = CSR_AW'(...);
localparam [CSR_AW-1:0] SLV_<BLOCK_NAME>_ADDR_E = CSR_AW'(...);
```

- `ADDR_E = offset + bytesize - 1`。
- demux 使用 `addr >= ADDR_S && addr <= ADDR_E`。
- demux 的起止地址比较必须写在同一个 `if` 行。
- slave 的 `<BLOCK_NAME>` 来自被引用文件的 block 名，不使用 slave
  `reg_name`；mem 使用自身 `reg_name`。
- 同一父 block 内重复引用同名 block 时，依次添加 `_U1`、`_U2`。
- TX 本地地址使用 `i_csr_req_addr - SLV_<BLOCK_NAME>_ADDR_S`。
- 后续逻辑不得重复嵌入 slv 起止地址的裸 `CSR_AW'(32'h...)`。

TX CSR bus 的 `o_tx_csr_req_write` 端口后必须用单行注释注明索引对应的
block：

```systemverilog
output wire [1:0] o_tx_csr_req_write, // [0]=block_a, [1]=block_b
```

每个 `o_tx_csr_req_valid[index]` 的 valid、clear、切换阻塞和 slv 选择条件
必须写在同一个 assign 行。

写请求：

- 按地址直接路由。
- ready 来自选中 slv。
- 不等待写 response。

读请求：

- local 视为 slv 0，其余 slv 从 1 编号。
- `r_read_slv` 记录当前 outstanding 读目标。
- `r_otf_cnt` 记录已接受读请求减已返回 response。
- `r_read_slv` 与 `r_otf_cnt` 必须使用两个独立的时序 always 块。
- `r_read_slv` 只在 `b_read_fire && (r_otf_cnt == '0)` 时更新。
- `r_otf_cnt` 只在 `b_read_fire || b_rsp_fire` 的 `else if` 分支中更新，
  其他周期自然保持。
- `r_otf_cnt` 在更新分支直接执行
  `r_otf_cnt <= r_otf_cnt + b_read_fire - b_rsp_fire;`，不要使用 case
  分别描述加一、减一和保持。
- 同一 slv 允许连续 outstanding 读。
- outstanding 非零时切换到另一 slv，必须反压新读请求。
- outstanding 清零后才允许切换，保证无 ID bus 的返回顺序。
- local read response 使用一级 valid/data 寄存器。

固定 localparam：

```systemverilog
localparam integer CSR_REQ_OSD_NUM = 256;
localparam integer OTF_CNT_W = $clog2(CSR_REQ_OSD_NUM);
localparam integer SLV_SEL_W = <clog2(slv_count + 1)，最少 1>;
```

所有 `SLV_LOCAL`、`SLV_<BLOCK_NAME>` selector 与 `SLV_<BLOCK_NAME>_ADDR_S/E`
localparam 必须连续分组输出，中间不插入 `CSR_INVALID_RDATA` 或 `REG_*_ADDR`。

每个非 slave/mem 寄存器地址也必须生成 localparam，并在 read decode、
cfg/cmd write decode 和 IRQ clear 中引用，不能重复写地址字面量：

```systemverilog
localparam [CSR_AW-1:0] REG_<REG_NAME>_ADDR = CSR_AW'(...);
```

repeat 寄存器的每个元素独立生成：
`REG_<REG_NAME>_0_ADDR`、`REG_<REG_NAME>_1_ADDR`，依次类推。
第一个 `REG_*_ADDR` 前空一行，与前面的 localparam 分组分隔。
同一模块内所有 `REG_*_ADDR` localparam 按最长名称补空格，`=` 必须对齐。

不要生成未使用的 `SLV_NUM`，不要生成未使用的 `b_req_is_write`。

### 9.9 RTL 代码风格

必须满足：

- module、signal、instance 全小写。
- parameter/localparam 全大写。
- 常规信号只用 `wire/reg`。
- struct/typedef 内可以使用 `logic`。
- DFF 使用 `reg` 和 `r_` 前缀。
- 组合 reg 使用 `w_` 前缀。
- 单 bit 组合条件推荐 `b_`。
- 时序逻辑只用 `always @(posedge clk or negedge rst_n)`。
- DFF 的 reset 或 clear 分支只有一条赋值时省略 `begin/end`；分支内有多条
  赋值时保留 `begin/end`。
- 组合逻辑只用 `always @*` 或 `assign`。
- 输出信号优先由 `assign` 驱动；组合过程驱动的 ready 声明为 output reg。
- 代码块顺序：localparam、signal、output assign、statement、instance。
- 注释只能是英文 `//` 行注释。
- 生成 RTL 中不能出现中文或 `/* ... */`。
- 一个 `.sv` RTL 文件最多一个 module。

### 9.10 typedef 与 wrapper

typedef 文件按存在的类型生成 packed struct：

```text
<block>_cfg_ts
<block>_status_ts
<block>_cmd_ts
<block>_irqsta_ts
<block>_irqclr_ts
```

wrapper：

- include typedef 文件。
- bus 和 slv bus 保持展开。
- cfg/status/cmd/irq 使用 struct 聚合。
- 实例名为 `u_<module>_<tag>` 形式。
- 子模块端口不能直接连接 wrapper 端口。
- 每个实例端口创建 `u_csr_i_*` 或 `u_csr_o_*` 中间 wire。
- 所有子模块输入在 instance 前通过 assign 赋值。
- 所有 wrapper 输出通过 assign 从 `u_csr_o_*` 驱动。
- 每个实例端口显式一行连接。
- wrapper 端口同样使用统一五列对齐和最后 `//,`。

集成模板 `tmp_<block>.sv` 当前只需给出英文说明，提示用户可以选择普通展开端口或
struct wrapper。

---

## 10. Testbench 与 UVM RAL

接口：

```python
generate_tb(module, out_dir) -> list[Path]
```

对树中每个唯一 source module 生成：

```text
out/tb/<block>_tb.sv
out/tb/<block>_ral_pkg.sv
```

### 10.1 Smoke Testbench

- 10ns clock。
- 异步低有效复位。
- 提供 `csr_write` 和 `csr_read` task。
- slv ready 默认全 1，slv response 默认 0。
- 自动选择一个无 shadow 的 cfg/cmd 做 write/read 检查。
- 若有 status，驱动第一个 status field 并检查读取。
- 成功打印 `<block>_tb PASS`。
- 使用 `$fatal` 报错。
- 显式例化 DUT 的所有端口。

### 10.2 UVM RAL

- package 名 `<block>_ral_pkg`。
- import `uvm_pkg::*`，include `uvm_macros.svh`。
- 每个非 slave/mem 寄存器生成一个 `uvm_reg` class。
- 每个 field 创建 `uvm_reg_field` 并 configure。
- volatile 对 status/irq 为 1，其余为 0。
- block class 名 `<block>_reg_block`。
- 每个成员使用 `reg_<reg_name>`，避免 `config` 等上下文关键字直接成为成员名。
- repeat 生成数组并循环 add_reg。
- map byte width 使用 `module.word_bytes`。
- 完成后 `lock_model()`。

---

## 11. Firmware Header

接口：

```python
generate_firmware(module, out_dir, is_nested=False) -> list[Path]
```

只在 nested 模式生成：

```text
out/firmware/<root>_all_reg_addr.h
out/firmware/<root>_all_reg_type.h
```

### 11.1 addr header

- include guard。
- 每种唯一 source block 的寄存器 offset 和 default 宏。
- repeat 每个实例独立宏，名字带 `_0`、`_1`。
- 不为 slave/mem 生成寄存器宏。
- 按树顺序生成每个节点 base address 和每个寄存器 absolute address。
- `system_prefix` 为空时使用 root module 名。
- 同名 block 在树中出现多次时，实例地址前缀使用 `_u1`、`_u2`。

### 11.2 type header

- include `<stdint.h>` 和 addr header。
- 不定义 `u32`，直接使用 `uint32_t` 或 `uint64_t`。
- bitwidth <= 32 使用 `uint32_t`，大于 32 使用 `uint64_t`。
- 每个非 slave/mem 寄存器生成 union：
  - `bits` struct。
  - 空洞生成 `rsv<msb>_<lsb>`。
  - `word` 标量。
- 每个 block 生成 `<block>_block_reg_ts`。
- repeat 成为 C 数组。
- Header 只能包含宏和类型声明，不定义静态对象，不分配程序存储空间。
- 注释使用英文 `//`。

---

## 12. 输入转换脚本

### 12.1 Markdown 到 XLSX

`input/xlsx/convert_md2xlsx.py`：

- 遍历 `input/*.md`。
- 使用主 parser 和 doc generator，不复制另一套解析逻辑。
- 输出 `input/xlsx/<clean_block_name>.xlsx`。
- 将 slave 的 `slv_filename` 扩展名改为 `.xlsx`，并使用 clean block name。
- 这样 `input/xlsx/top.xlsx -m nested` 可以直接递归运行。

### 12.2 Markdown 到 JSON

`input/json/convert_md2json.py`：

- 遍历 `input/*.md`。
- 使用 parser 和 `ModuleModel.to_dict()`。
- 输出 `input/json/<clean_block_name>.json`。
- 将 slave 的 `slv_filename` 扩展名改为 `.json`。
- 这样 `input/json/top.json -m nested` 可以直接递归运行。

---

## 13. 自动测试

使用标准库 `unittest`，文件为 `test_parser.py`。至少实现以下 8 项：

1. nested address map 和重复 reg_name 去重。
   - 检查 `test1..test4`。
   - 检查 `top/mid_a/leaf_a1 = 0xF0001100`。
   - 检查 `top/mid_b/leaf_a2 = 0xF0002100`。

2. 生成 Markdown 回灌幂等。
   - 输入 `leaf_a1_reg.md`。
   - 生成 `leaf_a1_gen.md`。
   - 重新解析后比较 name、offset、reg_type、default_word。

3. 地址 overlap 必须报错。

4. field 使用保留字必须报错。

5. ModuleModel JSON round trip。

6. `repeat 2, shadow 4` 与 irq RTL 生成。
   - 检查 `SHADOW_DEPTH = 4`。
   - 检查 working FIFO 写入。
   - 检查 irq clear assign。
   - 检查不出现 `always_ff`。

7. RTL 端口列对齐。
   - nested 生成 top。
   - 所有 input/output 的 signal name 起始列一致。
   - 所有真实逗号和末尾 `//,` 列一致。

8. nested HTML 寄存器详情表。
   - 存在 `register-table`。
   - 存在当前规范的属性和 field 表头。
   - 只显示合并后的 `SW_access`。
   - 不显示独立的 `SW` 或 `HW` 表头。

运行：

```bash
python -B -m unittest -v
```

预期：8 项全部通过。

---

## 14. 验收命令

在 `csr_tool/` 下执行：

```bash
python -B -m compileall -q src input/xlsx input/json test_parser.py
python -B -m unittest -v

python -B input/xlsx/convert_md2xlsx.py
python -B input/json/convert_md2json.py

python -B src/autogen_reg.py -i input/top_reg.md -m nested -o out
python -B src/autogen_reg.py -i input/xlsx/top.xlsx -m nested -o out/from_xlsx
python -B src/autogen_reg.py -i input/json/top.json -m nested -o out/from_json
```

Markdown top nested 当前应生成 41 个文件：

- 文档：每个节点 Markdown + tree Markdown/HTML/XLSX。
- RTL：5 个唯一模块，每个 4 个文件，共 20。
- TB/RAL：5 个唯一模块，每个 2 个文件，共 10。
- Firmware：2 个 Header。

JSON 输入比 Markdown/XLSX 多一个 tree JSON。

若环境存在 `pyslang`，增加：

- 解析 `out/rtl/**/*.sv` 和 `out/tb/*.sv`。
- 忽略未加载 UVM 宏造成的 `UnknownDirective`。
- 主 RTL 与对应 TB 组合做 semantic compilation。
- 主 RTL、typedef、wrapper 合并到同一 compilation unit 做 semantic compilation。

当前基准：

```text
Python unittest:       8/8 pass
SV syntax:             30 files, 0 failures
RTL + TB semantics:     5 pairs, 0 failures
```

还要执行文本风格扫描，生成 RTL/TB 中不得出现：

```text
中文字符
always_ff
always_comb
/* 或 */
大写 module 名
input logic
output logic
```

最后执行：

```bash
git diff --check
```

---

## 15. 实现顺序

严格按以下顺序工作，每一步运行局部测试：

1. `models.py`
2. `reg_common.py`
3. `reg_parser.py`
4. Markdown 幂等测试和 nested 地址测试
5. `reg_gen_doc.py`
6. `reg_gen_firmware.py`
7. `reg_gen_rtl.py`
8. shadow、irq、slv read ordering
9. typedef 和 wrapper
10. `reg_gen_tb.py`
11. CLI
12. XLSX/JSON 转换脚本
13. 全部 7 项单测
14. 三种输入 nested 端到端
15. SV 语法、语义、风格和 whitespace 验收

不要在 parser 中混入字符串模板，不要在各生成器重复解析 special，不要把绝对地址写回
RegisterModel，不要为了通过样例而硬编码模块名。

完成后简洁报告：

- 修改的模块。
- 测试数量。
- 三种输入是否端到端通过。
- SV 语法和语义检查结果。
- 当前环境无法执行的检查。
