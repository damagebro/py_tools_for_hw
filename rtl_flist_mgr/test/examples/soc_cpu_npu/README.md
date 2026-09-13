# soc_cpu_npu

本例的 dir 统一相对 TOML 所在目录：CPU filelist 中用 `..`、`../alu`、`../lsu` 指向 RTL。生成命令可显式使用 `-w .`；如需在子目录调用，先在本例根目录运行 `python -B ../../../src/rtl_flist_mgr.py --init-root -w .`，再用 `--show-root` 检查。缓存不是 root 标记。

TOML files 和 SRAM legacy_f 均输出规范化绝对路径。legacy_f 会替换变量、展开 -f/-F、去除注释与空行，并按真实路径去重；相对路径以所在 .f 目录为基准。

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
    │   ├── filelist/{cpu,alu,lsu,dw_sim_model}.toml
    │   ├── filelist/sram_sim_model.f
    │   ├── cpu_subsys.sv
    │   ├── alu/alu_harden_top.sv
    │   ├── alu_harden_stub.sv
    │   └── lsu/{lsu_harden_top.sv,model/}
    └── npu/{npu.toml,npu_subsys.sv}
```

本例将 CPU 的 core TOML 与 SRAM legacy `.f` 集中于 `import/cpu/filelist/`；`sram_sim_model.f` 使用 `${SRAM_PATH}`，通过 `--var SRAM_PATH=<模型目录绝对路径>` 传入。这样示例不会包含无效的 `/path/to/...` 占位路径。实际项目仍推荐在 legacy `.f` 中直接维护已部署模型的真实绝对路径；变量方式仅用于模型目录因环境而异的情况。`soc.toml` 与 `import/npu/npu.toml` 保持在原目录，用于对比两种组织方式。

## 三种模式

| mode    | CPU ALU                             | CPU LSU                   | LSU SRAM/DW model |
| ------- | ----------------------------------- | ------------------------- | ----------------- |
| `sim`   | 展开 `dmg:cpu:alu_harden`           | 展开 `dmg:cpu:lsu_harden` | 输出              |
| `synth` | 输出用户维护的 `alu_harden_stub.sv` | 不展开                    | 不输出            |
| `lint`  | 展开 `dmg:cpu:alu_harden`           | 展开 `dmg:cpu:lsu_harden` | 不输出            |

`alu_harden_stub.sv` 只定义一个 module，但 module 名仍是 `alu_harden_top`，以替代原始 `alu_harden_top.sv` 并满足综合链接。

## 运行

工具直接按 workspace 与 `import/*/` 扫描。可在本目录执行：

```bash
python -B ../../../src/rtl_flist_mgr.py --core dmg:soc:top -w . -m sim   --var SRAM_PATH=<模型目录绝对路径> -o out/soc_sim.f
python -B ../../../src/rtl_flist_mgr.py --core dmg:soc:top -w . -m synth -o out/soc_synth.f
python -B ../../../src/rtl_flist_mgr.py --core dmg:soc:top -w . -m lint  -o out/soc_lint.f
```
