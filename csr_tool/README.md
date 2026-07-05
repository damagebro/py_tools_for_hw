# CSR Autogen Tool

CSR Autogen Tool 是一款轻量级的寄存器自动化生成工具。它解析 Markdown、Excel 或 JSON 寄存器描述，生成文档、SystemVerilog RTL、自检 Testbench、UVM RAL 模型以及 Firmware C Header。

## 1. 运行指南 (Usage)

环境要求：Python 3.x。
可选依赖：`jinja2` (用于生成高级 HTML), `openpyxl` (用于生成/解析 Excel)。
即使不安装可选依赖，工具依然可以正常运行并生成基础的 Markdown 文件。

```bash
# 默认模式 (Single)：仅解析并输出当前指定的单个模块
python3 src/autogen_reg.py -i input/top_reg.md

# 嵌套模式 (Nested)：解析顶层模块并递归展开所有子模块，生成树形结构的文档
python3 src/autogen_reg.py -i input/top_reg.md --nested

# 等价写法
python3 src/autogen_reg.py -i input/top_reg.md -m nested -o out
```

```bash
# 将 input/*.md 转换为 input/xlsx/*.xlsx
python3 input/xlsx/convert_md2xlsx.py

# 以 Excel 作为输入运行嵌套模式
python3 src/autogen_reg.py -i input/xlsx/top_reg.xlsx --nested
```

```bash
# 将 input/*.md 转换为 input/json/*.json
python3 input/json/convert_md2json.py

# 以 JSON 作为输入运行嵌套模式，并输出 JSON 文档
python3 src/autogen_reg.py -i input/json/top_reg.json --nested
```

如果正在用 Excel/WPS 打开 `input/xlsx/*.xlsx`，转换脚本可能无法覆盖对应文件，需要先关闭表格后再重新转换。

## 2. 寄存器定义规范 (single 模式)

**填表方式与规则**：
1. **文件格式**：推荐使用 Markdown 表格格式（也支持 Excel）。包含两个主要部分：`# base_info` 和 `# reg_define`。
2. **base_info (选填)**：定义模块的基础信息，如 `reg_bitwidth`（通常为32）、`system_baseaddr`、`system_bytesize` 等。如果不填，工具会使用默认值。
3. **reg_define**：定义寄存器列表。包含 `offset`, `reg_name`, `field`, `msb`, `lsb`, `SW_access`, `default_value`, `reg_type`, `special`, `description` 等列。
4. **寄存器类型 (`reg_type`) 与读写属性 (`SW_access`) 绑定关系**：
   - `cfg`, SW_access=RW: 配置寄存器（软件可读写，硬件只读）。
   - `status`, SW_access=RO: 状态寄存器（硬件可写，软件只读）。
   - `toggle`, SW_access=W1T: 翻转触发寄存器（用于软件向硬件发送命令，硬件检测翻转产生脉冲）。
   - `irq`, SW_access=W1C: 中断寄存器（写1清0，用于中断状态清除等）。
   - `slave`, SW_access=留空: 子模块占位符（配合 `special` 列使用，用于嵌套模式）。
   - `mem`, SW_access=留空: 内存空间占位符（表示一段连续的 SRAM/Memory 空间）。
5. **特殊属性 (`special`)**：用于定义高级行为，多个属性用逗号分隔：
   - `slv_filename=xxx.md`: 仅当 `reg_type=slave` 时有效，指定子模块的定义文件路径。
   - `bytesize=0x...`: 指定 `slave` 或 `mem` 占用的地址空间大小。如果不填，工具会自动推导。
   - `repeat N`: 表示该寄存器（或配置组）连续重复 N 次，工具会自动分配地址空间。
     `default_value` 支持用 CSV 逗号分隔方式为每个 repeat 实例填写不同默认值；如果填写数量少于 N，后续实例沿用最后一个默认值。例如 `repeat 4` 且 `default_value=0x12,12` 时，默认值展开为 `[0]=0x12`, `[1]=12`, `[2]=12`, `[3]=12`。
   - `shadow` / `shadow N`: 仅对 `reg_type=cfg` 有效。硬件使用 working_reg 工作时，软件可以提前更新 shadow_reg，从而掩盖下一组配置的写入延时；`shadow N` 用 FIFO 机制维护 N 份 working_reg。
6. **填写技巧**：
   - `offset` 可以留空：工具会自动根据上一个寄存器的地址和位宽推导当前地址。
   - `reg_name` 可以重复：工具会自动去重并编号（如 `name1`, `name2`）。
7. **规则约束**：
   - `offset` 必须单向递增，不能重叠。
   - 字段的 `msb` 和 `lsb` 必须在 `reg_bitwidth` 范围内，且同一寄存器内的字段不能重叠。
   - `description` 列用于填写寄存器或字段的详细描述。

## 3. 系统级集成与地址映射 (nested 模式)

当使用 `--nested` 参数时，工具会从顶层模块开始，根据 `special` 列中的 `slv_filename=xxx.md` 递归解析所有子模块。

**嵌套模式核心功能**：
- **全局地址映射 (Address Map)**：自动计算并展示整个系统的地址分配树。
- **地址推导与校验**：自动推导未明确指定 `bytesize` 的子模块的地址空间，并严格校验各个子模块之间是否发生地址重叠 (Overlap) 或超出父节点分配的空间。

## 4. 架构设计与二次开发 (Developer Guide)

本工具的核心在于将非结构化的文本表格转换为结构化的内存对象，方便后续的 RTL/TB/FW 生成。

**核心数据结构 (`src/models.py`)**：
- `BaseInfoModel`: 存储模块的基础信息（基地址、位宽等）。
- `FieldModel`: 存储单个寄存器字段的信息（msb, lsb, 读写属性等）。
- `RegisterModel`: 存储单个寄存器的信息，包含一个 `FieldModel` 列表。
- `SubModuleNode`: 用于构建树形结构，包含子模块的实例化信息（如 `bytesize`）和指向子模块 `ModuleModel` 的指针。
- `ModuleModel`: 核心模块节点，包含 `BaseInfoModel`、`RegisterModel` 列表以及 `SubModuleNode` 列表。

**单模块 Register 与 Field 遍历示例 (Single 模式)**：
在生成单模块的 RTL 或 C Header 时，可以直接遍历 `registers` 和 `fields`：

```python
def traverse_module_regs(module: ModuleModel):
    print(f"Module: {module.name}")
    for reg in module.registers:
        print(f"  Reg: {reg.name} [Offset: {hex(reg.offset)}, Type: {reg.reg_type}]")
        for field in reg.fields:
            print(f"    Field: {field.name} [{field.msb}:{field.lsb}] - {field.sw_access} - Default: {field.default_value}")
```

**Tree 结构遍历示例 (Nested 模式)**：
在生成全局文档或集成 RTL 时，可以通过递归遍历 `ModuleModel` 的 `sub_modules` 来访问整个寄存器树：

```python
def traverse_tree(module: ModuleModel, depth=0):
    print("  " * depth + f"Module: {module.name}")
    for reg in module.registers:
        print("  " * (depth + 1) + f"Reg: {reg.name} at {reg.offset}")

    for sub_node in module.sub_modules:
        # 递归遍历子模块
        traverse_tree(sub_node.module_obj, depth + 1)
```

## 5. 输入输出文件格式

**输入格式**：
支持以下三种格式作为输入：
- `.md`: Markdown 表格格式（推荐，纯文本易于版本控制）。
- `.xlsx`: Excel 格式（方便表格编辑）。
- `.json`: JSON 格式（方便与其他工具链交互）。

**Single 模式输出格式**：
运行后，在 `out/doc/` 目录下会生成当前模块文档：
- `*_gen.md`: 格式化对齐的 Markdown 文档。
- `*_gen.xlsx`: Excel 格式的寄存器定义（需 `openpyxl`）。
- `*_gen.json`: 仅当输入文件是 `.json` 时生成。

同时生成：
- `out/rtl/${block}.sv` 与 `out/rtl/plus/` 下的 typedef、wrapper、集成模板。
- `out/tb/${block}_tb.sv` 自检 Testbench。
- `out/tb/${block}_ral_pkg.sv` UVM RAL 模型。

**Nested 模式输出格式**：
除了生成各个单模块的上述文件外，还会额外生成包含全局地址映射的树形文档：
- `*_tree.md`: 包含全局 Address Map 和所有子模块的 Markdown 文档。
- `*_tree.xlsx`: 包含 Sheet 导航栏的完整 Excel 文档（需 `openpyxl`）。
- `*_tree.html`: 包含全局 Address Map 和所有子模块展开的完整 HTML 文档（需 `jinja2`）。
- `*_tree.json`: 仅当输入文件是 `.json` 时生成，包含完整寄存器树结构的 JSON 数据。

嵌套模式还会在 `out/firmware/` 生成 `*_all_reg_addr.h` 和
`*_all_reg_type.h`。前者提供 offset、默认值和绝对地址宏，后者仅包含
寄存器 union/struct 类型声明，不分配静态存储空间。

## 6. 硬件 CSR 与 RTL 生成说明

硬件 CSR 的目标是把软件可见的寄存器访问，转换成 RTL 内部稳定、清晰、可集成的控制/状态接口。`csr_tool` 当前支持生成单模块 CSR RTL，主输出位于 `out/rtl/${block}.sv`。`block`由输入模块名规范为小写，实际生成的RTL模块名和文件名也使用小写。大多数用户只需要直接使用这个主文件；增强辅助文件放在 `out/rtl/plus/`，包括 typedef、struct wrapper 和集成模板。

### 6.1 csr_bus 接口特点

当前 CSR bus 采用“请求通道 + 读响应通道”的轻量协议：

- `csr_req_valid/csr_req_ready` 完成读写请求握手。
- `csr_req_write=0` 表示读请求，`csr_req_write=1` 表示写请求。
- 写请求只依赖 request ready 反压，不额外返回写响应。
- 读请求通过 `csr_rsp_rvalid/csr_rsp_rdata` 返回读数据。
- bus 支持连续写、连续读以及一定程度的 outstanding 读请求。
- bus 不带 request id，因此 CSR demux 在跨 slave/mem 目标切换时会等待已有读响应返回，保证读返回顺序不乱序。

连续访问时序如下图所示：

![csr_bus连续读写时序](doc/assets/csr_bus_timing.png)

WaveDrom 源文件：[`doc/assets/csr_bus_timing.json`](doc/assets/csr_bus_timing.json)

### 6.2 autogen_rtl 与 user_rtl 的 DFF 边界

`reg_type` 决定寄存器字段的 DFF 位于自动生成 CSR 模块内部，还是由用户 RTL 维护：

- `cfg`：DFF 在 `autogen_rtl` 内部。软件写配置值，硬件通过 `o_cfg_*` 或 wrapper struct 读取配置。
- `status`：DFF 在 `user_rtl` 内部。硬件维护状态，CSR 模块通过 `i_sta_*` 采样并提供软件读取。
- `cmd`：DFF 在 `autogen_rtl` 内部。W1T 字段写 1 翻转，软件可读回当前值，硬件消费 `o_cmd_*`。
- `irq`：中断状态 DFF 在 `user_rtl` 内部。CSR 模块读取 `i_irqsta_*`，并根据 W1C 写入产生 `o_irqclr_*` 清除脉冲。

边界关系如下图所示：

![reg_type dff architecture](doc/assets/reg_type_dff_arch.png)

### 6.3 cfg shadow 机制

`shadow` 用于解决配置切换延时问题：硬件继续使用当前 working_reg 工作时，软件可以提前把下一组配置写入 shadow_reg；等 user RTL 需要切换配置时，再用更新脉冲把 shadow_reg 提交到 working_reg。它只对 `reg_type=cfg` 生效，生成规则如下：

- `shadow` 与 `shadow 1` 等价：每个 cfg field 额外生成一份 `r_shd_${reg}_${field}`。CSR bus 写 shadow_reg，软件读和 user RTL 看到的是 working_reg；`i_pulse_shadow_upen` 到来时，shadow_reg 提交到 working_reg。
- `shadow N` 且 `N >= 2`：shadow_reg 仍然只有一份，working_reg 变成 N 份数组。`i_pulse_shadow_upen` 表示 push，把当前 shadow_reg 写入 `working[wr_idx]`；`i_pulse_shadow_rden` 表示 pop，让 user RTL 消费下一份 working 配置。
- 同一个模块中，所有 `shadow N >= 2` 的 N 必须相同，否则生成器会报错；`shadow`/`shadow 1` 可以和 `shadow N>=2` 同时存在。
- `o_dbg_shadow_wr_idx`、`o_dbg_shadow_rd_idx` 和 `o_dbg_shadow_water_level` 用于观察 FIFO 状态。`water_level` 表示还能容纳多少份配置，空时为 N，满时为 0。
- `o_pulse_err_write_when_full` 与 `o_pulse_err_read_when_empty` 为组合逻辑输出，分别表示满时 push、空时 pop 的非法操作。

shadow 数据流如下图所示：

<img alt="cfg shadow mechanism" src="doc/assets/cfg_shadow_mechanism.png" width="600">

### 6.4 RTL 输出结构

Single 模式下，RTL 输出默认分两层：

```text
out/rtl/${block}.sv
out/rtl/plus/${block}_typedef.sv
out/rtl/plus/${block}_wrap.sv
out/rtl/plus/tmp_${block}.sv
```

- `${block}.sv`：主 CSR RTL，端口保持展开形式，方便直接接入现有设计。
- `${block}_typedef.sv`：共享 typedef 文件，供 wrapper 和 user RTL 共同 include。
- `${block}_wrap.sv`：用 SystemVerilog `struct` 聚合 `cfg/status/cmd/irq` 接口，减少顶层端口数量。
- `tmp_${block}.sv`：临时集成模板，展示 autogen RTL 与 user RTL 的普通端口连接方式，以及 struct 版本接口写法。
