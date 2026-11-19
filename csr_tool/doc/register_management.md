# 寄存器管理约定

## 管理原则

采用分布式生成、统一存放、按需引用的方式。各 subsys 独立维护寄存器输入和 RTL/TB，SoC 层管理集成地址与入口，不重复展开下级全部产物。

本文是后续实现和项目使用的目标约定，不代表当前脚本已经支持全部输出布局与轻量集成功能。

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

- SoC 头文件提供各 subsys 的实际基地址，不复制各 subsys 的寄存器定义。
- subsys 头文件提供相对 subsys 基地址的偏移，不固化 SoC 部署地址。
- 寄存器实际地址为 SoC 分配的 subsys 基地址加 subsys 内偏移；公共 block 的寄存器偏移进一步叠加到实例偏移上。
- 固件按需包含 CPU、NPU 或 PERI 的头文件，不要求包含全部 subsys。
- subsys 相关符号保持各自命名空间，公共 block 的定义统一引用 `fw/common/`。

SoC 集成入口的具体文件名和存放位置后续确定，不能改变 subsys 产物可独立使用的原则。

### RTL 与 TB

- SoC 只生成本层需要的寄存器、地址分发逻辑及对应 TB。
- 下级 subsys 的 RTL/TB 使用各自已经交付的文件，不重复生成或覆盖。

## 更新与交付

1. 修改某个 subsys 的 Excel 后，重新生成该 subsys，更新其 RTL/TB 和 DOC/FW。
2. 仅下级寄存器变化、SoC 分配的地址范围不变时，SoC 层无需重新汇总下级完整内容。
3. subsys 基地址或占用范围变化时，同步更新 `soc_top.xlsx` 和 SoC 集成入口。
4. 公共 block 变化时，检查并更新所有引用方，统一交付匹配的 common 定义。
5. CSR 文档交付只保留 SoC 入口、各 subsys 根节点的 `*_tree.html` 及必要资源，不拷贝内部 block 的独立文档；固件交付保留所需 subsys 头文件及其引用的公共定义。
