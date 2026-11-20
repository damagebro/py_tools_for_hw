# 寄存器管理约定

## 管理原则

采用分布式生成、统一存放、按需引用的方式。各 subsys 独立维护寄存器输入和 RTL/TB，SoC 层管理集成地址与入口，不重复展开下级全部产物。

**更新与交付**

1. 修改某个 subsys 的 Excel 后，重新生成该 subsys，更新其 RTL/TB 和 DOC/FW。
2. 仅下级寄存器变化、SoC 分配的地址范围不变时，SoC 层无需重新汇总下级完整内容。
3. subsys 基地址或占用范围变化时，同步更新 `soc_top.xlsx` 和 SoC 集成入口。
4. 公共 block 变化时，检查并更新所有引用方，统一交付匹配的 common 定义。
5. CSR 文档交付只保留 SoC 入口、各 subsys 根节点的 `*_tree.html` 及必要资源，不拷贝内部 block 的独立文档；固件交付保留所需 subsys 头文件及其引用的公共定义。

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
