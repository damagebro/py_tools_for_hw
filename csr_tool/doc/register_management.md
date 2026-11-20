# 寄存器管理约定

## 管理原则

采用分布式生成、统一存放、按需引用的方式。各 subsys 独立维护寄存器输入和 RTL/TB，SoC 层管理集成地址与入口，不重复展开下级全部产物。

**更新与交付**

1. 修改某个 subsys 的 Excel 后，重新生成该 subsys，更新其 RTL/TB 和 DOC/FW。
2. 仅下级寄存器变化、SoC 分配的地址范围不变时，SoC 层无需重新汇总下级完整内容。
3. subsys 基地址或占用范围变化时，同步更新 `soc_top.xlsx` 和 SoC 集成入口。
4. 公共 block 变化时，检查并更新所有引用方，统一交付匹配的 common 定义。
5. CSR 文档交付只保留 SoC 入口、各 subsys 根节点的 `*_tree.html` 及必要资源，不拷贝内部 block 的独立文档；固件交付保留所需 subsys 头文件及其引用的公共定义。
6. 硬件同时交付 PG（Program Guide）中的 PHAL sequence 伪代码，软件据此实现初始化与操作流程；寄存器定义或操作时序变化时同步更新 PG。

## 固定示例

SoC 包含 CPU、NPU、PERI 三个 subsys，三个 subsys 复用同一份 timer block 定义。

```text
soc_top
├── cpu_subsys
│   ├── cpu_ctrl
│   ├── uart
│   └── timer             common = true
├── npu_subsys
│   ├── npu_ctrl
│   ├── dma
│   └── timer             common = true
└── peri_subsys
    ├── peri_ctrl
    ├── gpio
    └── timer             common = true
```

### Excel 输入

寄存器以 `.xlsx` 维护，使用 `base_info`、`reg_define` 工作表。`reg_type = slave` 通过 `slv_filename` 引用下级 Excel。

```text
csr/
├── soc_top.xlsx
├── cpu/
│   ├── cpu_subsys.xlsx
│   ├── cpu_ctrl.xlsx
│   └── uart.xlsx
├── npu/
│   ├── npu_subsys.xlsx
│   ├── npu_ctrl.xlsx
│   └── dma.xlsx
├── peri/
│   ├── peri_subsys.xlsx
│   ├── peri_ctrl.xlsx
│   └── gpio.xlsx
└── common/
    └── timer.xlsx
```

- `soc_top.xlsx` 将三个 subsys 写成 `reg_type = mem`，分配各自的 SoC 地址范围；不填写 `slv_filename`，不引用或展开 subsys Excel。
- 每个 subsys 内部通过 `reg_type = slave` 引用自己的 block，并分配 block 在 subsys 内的地址偏移。
- 三个 subsys 均引用 `../common/timer.xlsx`，不复制三份 timer 表格。
- `timer.xlsx` 自身的 `base_info` 设置 `common = true`，该标记不传播到子模块。
- Excel 是寄存器定义源，生成的 HTML 和头文件不作为下级寄存器定义的解析输入。

## Subsys 独立生成

各 subsys 独立生成 RTL、TB、DOC、FW，产物按用途管理。

- RTL 拷贝到对应 subsys 的设计目录，由该 subsys 管理和集成。
- TB 拷贝到对应 subsys 的验证目录，由该 subsys 管理和运行。
- DOC 只将每个 subsys 根节点生成的 `*_tree.html` 拷贝到 CSR 根目录的 `subsys_out/doc/`，不拷贝 subsys 内部各 block 的独立文档。
- 根节点的 `*_tree.html` 保留 subsys 内部完整寄存器树及 block 详情，阅读时不依赖另行拷贝的 block 文档。
- FW 保留在 `subsys_out/fw/` 下，各 subsys 保持独立入口，公共定义集中到 `common/`。
- 生成缓存和临时文件不作为正式交付内容。

目标目录如下。各 subsys 的 FW 按地址、类型和兼容字段宏展开，不再用 `cpu.h` 等简写表示。

```text
csr/
├── soc_top.xlsx
├── cpu/
├── npu/
├── peri/
├── common/
│   └── timer.xlsx
└── subsys_out/
    ├── doc/
    │   ├── cpu_tree.html
    │   ├── npu_tree.html
    │   └── peri_tree.html
    └── fw/
        ├── common/
        │   ├── timer_reg_addr.h
        │   ├── timer_reg_type.h
        │   └── c_legacy/
        │       └── timer_field_macros.h
        ├── cpu_all_reg_addr.h
        ├── cpu_all_reg_type.h
        ├── npu_all_reg_addr.h
        ├── npu_all_reg_type.h
        ├── peri_all_reg_addr.h
        ├── peri_all_reg_type.h
        └── c_legacy/
            ├── cpu_field_macros.h
            ├── npu_field_macros.h
            └── peri_field_macros.h
```

### 公共 Block

- `fw/common/` 统一保留一套公共 block 定义，供各 subsys 头文件引用。
- 公共定义保留寄存器偏移、默认值、类型和字段宏，不包含某个实例的 SoC 绝对地址。
- 各 subsys 分别维护 timer 实例的地址信息，不因复用公共定义而合并实例。
- 独立生成后汇总 common 文件时，需确认同名定义一致，不能无条件互相覆盖。

## SoC 轻量集成

SoC 将各 subsys 作为 `reg_type = mem` 地址窗口管理，不再把 subsys 的完整寄存器树集中展开到一个大 HTML 或一套重复头文件中。详细定义仍由各 subsys 独立维护，SoC 地址窗口的大小需与 subsys 实际占用范围保持一致。

### 文档

- SoC 文档只展示本层寄存器、各 subsys 的基地址和地址范围。
- 集成文档通过相对链接跳转到 `subsys_out/doc/cpu_tree.html` 等独立文档；链接属于文档导航，不依赖 `mem` 节点递归解析下级 Excel。
- subsys 文档独立更新，每次仅替换对应根节点的 `*_tree.html`，不汇集内部 block 的独立文档；交付时保持导航链接及必要资源的相对目录关系。

### Firmware

- SoC 头文件提供各 subsys 的实际基地址，不复制各 subsys 的寄存器定义。不同 master 编译环境使用相同宏名，分别提供各自看到的基地址。
- subsys 头文件通过 `#ifndef` 为根节点的 `SYSTEM_ADDR` 宏提供默认值，默认值取输入表格的 `system_baseaddr`，未填写时为 `0`；集成时先定义该宏，再包含 subsys 头文件。
- 寄存器实际地址为 SoC 分配的 subsys 基地址加 subsys 内偏移；公共 block 的寄存器偏移进一步叠加到实例偏移上。
- 固件按需包含 CPU、NPU 或 PERI 的头文件，不要求包含全部 subsys。
- 每个 subsys root 只生成一个合并的地址头文件，内部普通 block 的地址宏直接展开在其中，不为每个 block 单独生成 `.h` 或文件保护宏；标记为 common 的公共定义仍单独提取。
- subsys 相关符号保持各自命名空间，公共 block 的定义统一引用 `fw/common/`。

SoC 集成入口的具体文件名和存放位置后续确定，不能改变 subsys 产物可独立使用的原则。

### RTL 与 TB

- SoC 只生成本层需要的寄存器、地址分发逻辑及对应 TB。
- 下级 subsys 的 RTL/TB 使用各自已经交付的文件，不重复生成或覆盖。

## PHAL Sequence 与 PG 交付

PHAL 在此表示项目级的软硬件访问适配层。生成的 FW 头文件负责地址、类型、默认值和字段宏；硬件通过 PG 定义寄存器初始化与操作序列，软件实现访问后端及正式驱动。下面仅约定接口与 sequence 伪代码，不增加 PHAL 源码自动生成。

### PG 编写与交付

- PHAL sequence 由硬件编写，保存在项目或 subsys 维护的 PG（Program Guide）文档的 `PHAL Sequence` 章节中，作为软硬件交接内容。
- PG 是人工维护的设计文档，纳入项目版本管理，不放进会被工具重新生成的 `out/` 目录，也不只保存在寄存器表格或生成头文件的注释中。
- sequence 使用生成的 struct、union 和 `.bits` 位域描述字段，通过 `set_reg/get_reg` 读写 `.word`，不固化 MCU/Host 的绝对地址。掩码接口作为底层可选工具，不作为 PG sequence 的主要表达方式。
- 每个 sequence 写明适用模块、前置条件、参数、操作顺序、等待条件、超时及失败处理；涉及电源、时钟、复位或其他模块的依赖也需明确。
- 软件以 PG 为依据实现和维护正式驱动，并适配各编译环境的地址视图、访问后端及并发控制。PG 中的伪代码不是直接交付的通用驱动源码。
- PG 随对应版本的 FW 头文件和寄存器文档一起交付。PG 说明“如何操作”，寄存器文档说明“每个寄存器是什么”，两者互相引用，不重复维护整套寄存器定义。

### 访问接口

MCU 与 Host 使用相同接口，但分别实现访问后端。`set_reg` 表示整字写入，不表示只置位某些 bit；`get_reg` 表示整字读取。

```cpp
#include <stdint.h>

// 平台实现: 地址使用当前编译环境的 SYSTEM_ADDR 视图。
uint32_t phal_read32(uintptr_t addr);
void phal_write32(uintptr_t addr, uint32_t value);

static inline uint32_t get_reg(uintptr_t addr)
{
    return phal_read32(addr);
}

static inline void set_reg(uintptr_t addr, uint32_t value)
{
    phal_write32(addr, value);
}

// 仅适用于整字均可安全读改写的普通 RW 配置寄存器。
// value 已经移位到对应字段，mask 之外的 bit 保持原值。
static inline void update_reg(uintptr_t addr, uint32_t mask, uint32_t value)
{
    uint32_t current = get_reg(addr);
    set_reg(addr, (current & ~mask) | (value & mask));
}

// 平台提供有超时的轮询: (get_reg(addr) & mask) == (expected & mask)。
// 返回 0 表示满足条件，负值表示超时或访问失败，禁止无限等待。
int wait_reg(uintptr_t addr, uint32_t mask, uint32_t expected, uint32_t timeout_us);
```

- MCU 后端使用平台提供的 MMIO 访问方式；Host 后端可使用映射后的设备窗口或驱动接口，不能直接把设备总线地址当作进程指针解引用。
- 地址转换、32-bit 对齐、字节序、设备内存属性和必要的访问屏障由平台后端处理。普通 `volatile` 访问不能替代这些平台约束。
- `update_reg` 不是原子操作。同一寄存器存在多线程、中断或多 master 访问时，由驱动提供互斥与所有权管理；软件锁不能阻止硬件自行更新字段。
- Host 访问失败应由后端显式上报，不能用返回 `0` 冒充成功读取。本例省略平台错误传递的具体实现。

### 常用初始化序列

初始化 sequence 由硬件在 PG 中编写，软件按其实现驱动，不能只根据寄存器表格的排列顺序自动推断。

```text
准备电源、时钟、复位和 Host 地址映射
    -> 确认设备可访问，必要时读取 ID/version
    -> 关闭目标功能
    -> 写配置，保持使能为 0
    -> 对允许回读的配置检查写入结果
    -> 按 W1C 规则清除历史中断状态
    -> 配置中断屏蔽并使能功能（若硬件提供相应寄存器）
    -> 按需写启动命令，并有超时地等待完成或就绪
```

下面使用现有 top/mid/leaf 示例中的 `leaf_a2`，展示可写入 PG 的 sequence 伪代码，演示 mode 配置、使能和 W1C 清除。示例假设时钟、复位已准备完成，且 `config` 可以安全读改写和回读；实际项目的复位、启动、等待条件需由硬件在对应 PG 中明确。

```cpp
// PG 中的 sequence 伪代码，软件按平台要求实现为正式驱动。
// 根地址由 MCU/Host 编译环境提前定义，也可沿用表格中的默认值。
#include "top_all_reg_addr.h"
#include "top_all_reg_type.h"

int npu_leaf_a2_init(uint32_t mode)
{
    const uintptr_t config_addr = NPU_LEAF_A2_U1_CONFIG_ADDR;
    leaf_a2_block_reg_ts regs;
    leaf_a2_config_tu current;
    leaf_a2_config_tu readback;

    // 仅初始化本地 struct，不会访问硬件。
    leaf_a2_block_reg_set_default(&regs);
    regs.config.bits.mode = mode;
    regs.config.bits.en = 0U;

    // 位域赋值可能截断，写硬件前检查参数是否可完整表示。
    if (regs.config.bits.mode != mode) {
        return -1;
    }

    // 普通 RW 配置可安全读改写，先关闭功能，保留其他当前配置。
    current.word = get_reg(config_addr);
    current.bits.en = 0U;
    set_reg(config_addr, current.word);

    // 按默认配置和目标 mode 写入，保持 en=0。
    set_reg(config_addr, regs.config.word);

    // 普通 RW 配置允许回读检查；失败时保持关闭，不继续启动。
    readback.word = get_reg(config_addr);
    if (readback.bits.mode != regs.config.bits.mode || readback.bits.en != 0U) {
        return -2;
    }

    // W1C 从零组字，仅将需要清除的位设为 1，不读改写。
    regs.int_sts.word = 0U;
    regs.int_sts.bits.err = 1U;
    set_reg(NPU_LEAF_A2_U1_INT_STS_ADDR, regs.int_sts.word);

    regs.config.bits.en = 1U;
    set_reg(config_addr, regs.config.word);
    return 0;
}

// top_ctrl.start 是 W1T 命令，系统其他初始化完成后按需调用。
void npu_start(void)
{
    top_top_ctrl_tu command;
    command.word = 0U;
    command.bits.start = 1U;
    set_reg(NPU_TOP_TOP_CTRL_ADDR, command.word);
}
```

struct/union 只作为本地组字与解码对象，不把整个 block struct 直接映射为 MMIO 布局，也不整体写回。实际访问始终使用对应寄存器的 `*_ADDR` 和 `.word`，避免访问 RO、W1C 或命令寄存器时产生副作用。位域与 `.word` 的映射依赖编译器 ABI 和端序，软件需分别验证 MCU/Host 工具链中的布局。

当前示例没有独立的 ready/done 寄存器，因此不虚构轮询地址。实际模块提供状态位后，再按其定义调用 `wait_reg`，超时返回上层处理。

### 特殊寄存器约束

- 普通 RW 配置可按字段掩码更新；完整写默认值仅用于明确允许的初始化场景，不能批量向所有寄存器写 DEFAULT。
- RO 状态只读；有读清除或 FIFO 出队等副作用的寄存器，不用于无条件轮询和重复回读。
- W1C 状态通过直接写 `1` 清除目标 bit，不读改写，避免误清其他已置位状态。
- W1T 命令直接写触发掩码，不读改写，也不把命令寄存器当作普通存储配置回读校验。
- shadow 配置的写入和提交顺序按具体模块协议执行，不能把多个阶段简化为一次 `update_reg`。

## 附录: 软件地址头文件（addr.h）

本章作为地址头文件参考附录。附录1说明 SoC 与 subsys 的分层组合方式，附录2展示当前脚本实际生成的 top/mid/leaf 地址宏。

宏定义不超过 120 字符时保持单行，仅超过 120 字符时使用反斜线续行。

### 附录1：SoC 与 Subsys 分层示意

CPU subsys 的全部普通 block 地址定义合并到 `cpu_all_reg_addr.h`，NPU subsys 合并到 `npu_all_reg_addr.h`。`cpu_ctrl` 只是 CPU 根地址头文件中的一个区段，不单独生成头文件。公共 timer 定义仍保留在 `common/timer_reg_addr.h`。

本小节使用简化的 `CPU_SYSTEM_ADDR`、`CPU_BASE_ADDR` 等宏名说明层级组合，实际生成的前缀与唯一化命名见附录2。`soc_top_addr.h` 为 SoC 基地址配置示意。

集成时先包含 SoC 基地址配置，再按需包含 subsys 根地址头文件。common 维护 block 内偏移，subsys 合并各实例偏移和根基地址，SoC 按编译环境提供根基地址。

以下使用 32-bit 地址，Host 的 CPU subsys 基地址为 `0x1000_0000`，MCU 的为 `0xFE00_0000`。NPU subsys 在各自视图中位于 CPU subsys 基地址加 `0x0001_0000`。C/C++ 十六进制常量不使用下划线分隔。

```cpp
// common/timer_reg_addr.h
#ifndef TIMER_REG_ADDR_H
#define TIMER_REG_ADDR_H

#define TIMER_CTRL_OFFSET   0x00U
#define TIMER_STATUS_OFFSET 0x04U

#endif
```

```cpp
// cpu_all_reg_addr.h: CPU subsys 唯一的根地址头文件
#ifndef CPU_ALL_REG_ADDR_H
#define CPU_ALL_REG_ADDR_H

#include "common/timer_reg_addr.h"

#ifndef CPU_SYSTEM_ADDR
#define CPU_SYSTEM_ADDR 0x00000000U
#endif

// cpu root
#define CPU_BASE_ADDR       (CPU_SYSTEM_ADDR + 0x00000000U)
#define CPU_REG1_ADDR       (CPU_BASE_ADDR + 0x00U)
#define CPU_REG2_ADDR       (CPU_BASE_ADDR + 0x04U)
#define CPU_CTRL_SLV_ADDR   (CPU_BASE_ADDR + 0x10U)
#define CPU_TIMER0_SLV_ADDR (CPU_BASE_ADDR + 0x20U)

// cpu/cpu_ctrl: 直接展开，不再增加文件保护宏或独立头文件。
#define CPU_CTRL_BASE_ADDR CPU_CTRL_SLV_ADDR
#define CPU_CTRL_REG1_ADDR (CPU_CTRL_BASE_ADDR + 0x00U)
#define CPU_CTRL_REG2_ADDR (CPU_CTRL_BASE_ADDR + 0x04U)

// cpu/timer0: 公共定义单独引用，实例地址在本文件展开。
#define CPU_TIMER0_BASE_ADDR   CPU_TIMER0_SLV_ADDR
#define CPU_TIMER0_CTRL_ADDR   (CPU_TIMER0_BASE_ADDR + TIMER_CTRL_OFFSET)
#define CPU_TIMER0_STATUS_ADDR (CPU_TIMER0_BASE_ADDR + TIMER_STATUS_OFFSET)

#endif
```

```cpp
// npu_all_reg_addr.h: NPU subsys 唯一的根地址头文件
#ifndef NPU_ALL_REG_ADDR_H
#define NPU_ALL_REG_ADDR_H

#include "common/timer_reg_addr.h"

#ifndef NPU_SYSTEM_ADDR
#define NPU_SYSTEM_ADDR 0x00000000U
#endif

#define NPU_BASE_ADDR          (NPU_SYSTEM_ADDR + 0x00000000U)
#define NPU_REG1_ADDR          (NPU_BASE_ADDR + 0x00U)
#define NPU_REG2_ADDR          (NPU_BASE_ADDR + 0x04U)
#define NPU_TIMER0_SLV_ADDR    (NPU_BASE_ADDR + 0x40U)
#define NPU_TIMER0_BASE_ADDR   NPU_TIMER0_SLV_ADDR
#define NPU_TIMER0_CTRL_ADDR   (NPU_TIMER0_BASE_ADDR + TIMER_CTRL_OFFSET)
#define NPU_TIMER0_STATUS_ADDR (NPU_TIMER0_BASE_ADDR + TIMER_STATUS_OFFSET)

#endif
```

```cpp
// soc_top_addr.h: MCU 编译环境
#ifndef SOC_TOP_ADDR_H
#define SOC_TOP_ADDR_H

#define CPU_SYSTEM_ADDR 0xFE000000U
#define NPU_SYSTEM_ADDR 0xFE010000U

#endif
```

```cpp
// SoC 固件: 先包含基地址定义，再按需包含 subsys。
#include "soc_top_addr.h"
#include "cpu_all_reg_addr.h"
#include "npu_all_reg_addr.h"

// CPU_REG1_ADDR          == 0xFE000000U
// CPU_REG2_ADDR          == 0xFE000004U
// CPU_CTRL_BASE_ADDR     == 0xFE000010U
// CPU_CTRL_REG1_ADDR     == 0xFE000010U
// CPU_CTRL_REG2_ADDR     == 0xFE000014U
// CPU_TIMER0_CTRL_ADDR   == 0xFE000020U
// NPU_REG1_ADDR          == 0xFE010000U
// NPU_REG2_ADDR          == 0xFE010004U
// NPU_TIMER0_STATUS_ADDR == 0xFE010044U
```

```cpp
// subsys 独立编译环境: 不包含 soc_top_addr.h，示例默认根地址为 0。
#include "cpu_all_reg_addr.h"

// CPU_REG1_ADDR        == 0x00U
// CPU_REG2_ADDR        == 0x04U
// CPU_CTRL_BASE_ADDR   == 0x10U
// CPU_CTRL_REG1_ADDR   == 0x10U
// CPU_CTRL_REG2_ADDR   == 0x14U
// CPU_TIMER0_CTRL_ADDR == 0x20U
```

```cpp
// soc_top_addr.h: Host 编译环境，替换 MCU 版本，不同时包含两份。
#ifndef SOC_TOP_ADDR_H
#define SOC_TOP_ADDR_H

#define CPU_SYSTEM_ADDR 0x10000000U
#define NPU_SYSTEM_ADDR 0x10010000U

#endif

// common/timer_reg_addr.h、cpu_all_reg_addr.h、npu_all_reg_addr.h 无需修改。
// 按相同顺序包含后，CPU_CTRL_REG2_ADDR == 0x10000014U。
```

### 附录2：实际生成格式

以 `input/top_reg.md` 的 top/mid/leaf 为例，`system_prefix = npu`，`system_baseaddr = 0xF0000000`。输出文件名仍为 `top_all_reg_addr.h`，寄存器偏移和默认值宏保持不变。

默认根地址下的 addr_map 如下，聚焦各级地址窗口和 leaf 的 `config` 寄存器，其他本地寄存器省略。`offset` 相对直接父节点，`size` 为分配的窗口大小，地址范围包含结束地址。

```text
top                                size=0x10000  [0xF0000000, 0xF000FFFF]
├── mid_a           offset=0x1000  size=0x0800   [0xF0001000, 0xF00017FF]
│   ├── leaf_a1     offset=0x0100  size=0x0040   [0xF0001100, 0xF000113F]
│   └── leaf_a2     offset=0x0200  size=0x0100   [0xF0001200, 0xF00012FF]  common, U1
│       └── config  offset=0x0004                0xF0001204
└── mid_b           offset=0x2000  size=0x0400   [0xF0002000, 0xF00023FF]
    ├── b_mem       offset=0x0010  size=0x0080   [0xF0002010, 0xF000208F]  mem
    └── b_slv       offset=0x0100  size=0x00C0   [0xF0002100, 0xF00021BF]  leaf_a2, common, U2
        └── config  offset=0x0004                0xF0002104
```

两处 `leaf_a2` 共用同一套寄存器偏移和默认值定义，但实例地址不同。对应关系为 `0xF0000000 + 0x1000 + 0x0200 + 0x0004 = 0xF0001204` 和 `0xF0000000 + 0x2000 + 0x0100 + 0x0004 = 0xF0002104`。`b_mem` 只展示地址窗口，不展开下级寄存器。

```cpp
// common/leaf_a2_reg_addr.h: 公共 block 只保存内部偏移和默认值。
#define LEAF_A2_CONFIG_OFFSET  0x00000004U
#define LEAF_A2_CONFIG_DEFAULT 0x00000001U
```

```cpp
// top_all_reg_addr.h，以下省略文件保护宏及其他寄存器。
#include "common/leaf_a2_reg_addr.h"

// top: SYSTEM_ADDR 默认取输入表格的 system_baseaddr。
#ifndef NPU_TOP_SYSTEM_ADDR
#define NPU_TOP_SYSTEM_ADDR 0xF0000000U
#endif

#define NPU_TOP_BASE_ADDR      (NPU_TOP_SYSTEM_ADDR + 0x00000000U)
#define NPU_TOP_SIZE           0x00010000U
#define NPU_TOP_END_ADDR       (NPU_TOP_BASE_ADDR + NPU_TOP_SIZE - 1U)
#define NPU_TOP_TOP_CTRL_ADDR  (NPU_TOP_BASE_ADDR + TOP_TOP_CTRL_OFFSET)
#define NPU_TOP_MID_A_SLV_ADDR (NPU_TOP_BASE_ADDR + 0x00001000U)
#define NPU_TOP_MID_B_SLV_ADDR (NPU_TOP_BASE_ADDR + 0x00002000U)

// top/mid_a: 子节点引用父节点导出的 slave 窗口。
#define NPU_MID_A_BASE_ADDR        NPU_TOP_MID_A_SLV_ADDR
#define NPU_MID_A_SIZE             0x00000800U
#define NPU_MID_A_END_ADDR         (NPU_MID_A_BASE_ADDR + NPU_MID_A_SIZE - 1U)
#define NPU_MID_A_MID_CFG_ADDR     (NPU_MID_A_BASE_ADDR + MID_A_MID_CFG_OFFSET)
#define NPU_MID_A_LEAF_A2_SLV_ADDR (NPU_MID_A_BASE_ADDR + 0x00000200U)

// top/mid_a/leaf_a2: common 定义复用，实例地址仍逐级计算。
#define NPU_LEAF_A2_U1_BASE_ADDR   NPU_MID_A_LEAF_A2_SLV_ADDR
#define NPU_LEAF_A2_U1_SIZE        0x00000100U
#define NPU_LEAF_A2_U1_END_ADDR    (NPU_LEAF_A2_U1_BASE_ADDR + NPU_LEAF_A2_U1_SIZE - 1U)
#define NPU_LEAF_A2_U1_CONFIG_ADDR (NPU_LEAF_A2_U1_BASE_ADDR + LEAF_A2_CONFIG_OFFSET)

// top/mid_b: slave 实例名为 b_slv，引用的 block 名仍是 leaf_a2。
#define NPU_MID_B_BASE_ADDR      NPU_TOP_MID_B_SLV_ADDR
#define NPU_MID_B_B_SLV_SLV_ADDR (NPU_MID_B_BASE_ADDR + 0x00000100U)
#define NPU_LEAF_A2_U2_BASE_ADDR NPU_MID_B_B_SLV_SLV_ADDR
```

`_SLV_ADDR` 使用父节点下的 slave 实例名；重复 block 的实例宏继续使用 `_U1`、`_U2` 等唯一化名称。只有根节点生成可覆盖的 `SYSTEM_ADDR`，不为每个下级 block 单独生成根地址宏。所有 `END_ADDR` 统一按 `BASE_ADDR + SIZE - 1U` 计算，算术表达式带括号。

```cpp
// Host 编译环境: 在包含生成头文件之前指定根地址。
#define NPU_TOP_SYSTEM_ADDR 0x10000000U
#include "top_all_reg_addr.h"

// NPU_MID_A_BASE_ADDR        == 0x10001000U
// NPU_LEAF_A2_U1_CONFIG_ADDR == 0x10001204U
```

```cpp
// MCU 编译环境: 与 Host 分开编译，使用相同的宏名和生成文件。
#define NPU_TOP_SYSTEM_ADDR 0xFE000000U
#include "top_all_reg_addr.h"

// NPU_MID_A_BASE_ADDR        == 0xFE001000U
// NPU_LEAF_A2_U1_CONFIG_ADDR == 0xFE001204U
```

不覆盖时，上述 leaf 寄存器地址为 `0xF0001204U`。也可通过编译选项 `-DNPU_TOP_SYSTEM_ADDR=0x10000000U` 指定根地址，不需要修改或重新生成头文件。该覆盖仅影响软件地址宏，不修改生成的 RTL/TB 或文档中的地址布局。
