# soc_cpu_npu

这是 `rtl_flist_mgr` 的固定回归与人工阅读示例，结构为 `soc -> cpu/npu`，CPU 进一步依赖 ALU/LSU harden core。

![soc_cpu_npu architecture](assets/soc_cpu_npu_arch.png)

## 目录

```text
soc_cpu_npu/
├── soc.toml
├── rtl/
│   ├── soc_pkg.sv
│   └── soc_top.sv
└── import/
    ├── cpu/
    │   ├── filelist/{cpu,alu,lsu}.toml
    │   ├── cpu_subsys.sv
    │   ├── alu/alu_harden_top.sv
    │   ├── alu_harden_stub.sv
    │   └── lsu/{lsu_harden_top.sv,model/}
    └── npu/{npu.toml,npu_subsys.sv}
```

本例仅将 CPU 的 core TOML 集中于 `import/cpu/filelist/`；`soc.toml` 与 `import/npu/npu.toml` 保持在原目录，用于对比两种组织方式。

## 三种模式

| mode    | CPU ALU                              | CPU LSU                          | LSU SRAM/DW model |
| ------- | ------------------------------------ | -------------------------------- | ----------------- |
| `sim`   | 展开 `dmg:cpu:alu_harden`            | 展开 `dmg:cpu:lsu_harden`        | 输出              |
| `synth` | 输出用户维护的 `alu_harden_stub.sv` | 不展开                           | 不输出            |
| `lint`  | 展开 `dmg:cpu:alu_harden`            | 展开 `dmg:cpu:lsu_harden`        | 不输出            |

`alu_harden_stub.sv` 只定义一个 module，但 module 名仍是 `alu_harden_top`，以替代原始 `alu_harden_top.sv` 并满足综合链接。

## 运行

工具直接按 workspace 与 `import/*/` 扫描。可在本目录执行：

```bash
python -B ../../../src/rtl_flist_mgr.py soc.toml -m sim   -o out/soc_sim.f
python -B ../../../src/rtl_flist_mgr.py soc.toml -m synth -o out/soc_synth.f
python -B ../../../src/rtl_flist_mgr.py soc.toml -m lint  -o out/soc_lint.f
```
