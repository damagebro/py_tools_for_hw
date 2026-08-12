# sim_axi_vip

`sim_axi_vip` 基于 `gen_tb_demo` 目录结构构建，提供一组直连的 AXI master/slave 测试环境。默认先连续写入全部数据，再连续读回并逐 beat 比较。

## 目录文件

| 文件                    | 说明                                        |
| --------------------- | ----------------------------------------- |
| `ENV.sh`              | 仿真环境变量和 `SIM_DIR` 初始化脚本                   |
| `Makefile`            | VCS/Xrun 常用仿真命令入口                         |
| `axi_vip.cfg`         | 单组 master/slave 的运行配置                       |
| `rtl.f`               | DUT RTL filelist，默认为空                     |
| `testbench.f`         | AXI VIP testbench filelist                |
| `tb/axi_interface.sv` | AXI interface 和 master/slave modport      |
| `tb/axi_master.sv`    | 可配置 AXI master 激励                         |
| `tb/axi_slave.sv`     | AXI slave memory                              |
| `tb/top.sv`           | 顶层时钟、复位和 VIP 连接                           |

## 常用命令

| 命令               | 说明                                        |
| ---------------- | ----------------------------------------- |
| `make com`       | 使用 VCS 编译 `rtl.f` 和 `testbench.f`         |
| `make run`       | 运行 VCS 仿真，默认读取 `../axi_vip.cfg`           |
| `make run TC=xx` | 指定 testcase 名运行 VCS 仿真                    |
| `make verdi`     | 使用 Verdi 打开波形和源码                          |

## 配置文件

默认配置文件是 `axi_vip.cfg`，运行时可覆盖：

```bash
make run AXI_CFG=../my_axi_vip.cfg
```

全局配置：

| 配置项             | 说明                                        |
| --------------- | ----------------------------------------- |
| `timeout_cycle` | top 等待全部 master done 的周期数                 |

master 使用 `m0.` 前缀，slave 使用 `s0.` 前缀。

master 配置：

| 配置项                           | 说明                                        |
| ----------------------------- | ----------------------------------------- |
| `m0.enable`                   | 是否启用 master                              |
| `m0.base_addr`                | 写事务起始地址                                   |
| `m0.byte_size`                | 写入并读回的数据总 byte 数                         |
| `m0.data_mode`                | `addr`/`data=addr`、`file` 或常量模式           |
| `m0.data_value`               | 常量数据模式使用的默认数据                             |
| `m0.data_file`                | `data_mode=file` 时读取的二进制文件                |
| `m0.axi_perf_mode`            | `full` 连续传输；`basic` 逐笔传输                  |
| `m0.axi_awvalid_mode`         | basic 模式下为 `continuous` 或 `random`         |
| `m0.axi_awvalid_gap_min/max`  | basic random 模式下 AWVALID 间隔范围             |

共享 slave 配置：

| 配置项                           | 说明                                        |
| ----------------------------- | ----------------------------------------- |
| `s0.enable`                   | 是否启用共享 slave                              |
| `s0.mem_size`                 | 共享 slave memory byte 容量                   |
| `s0.data_mode`                | `addr`/`data=addr`、`file` 或常量模式           |
| `s0.data_value`               | 常量初始化模式使用的默认数据                            |
| `s0.data_file`                | `data_mode=file` 时初始化 memory 的文件          |
| `s0.axi_perf_mode`            | `full` 连续响应；`basic` 逐笔响应                  |
| `s0.axi_reorder_depth`        | B response 乱序窗口；`0` 表示不乱序                 |
| `s0.axi_awready_mode`         | `continuous` 或 `random`                   |
| `s0.axi_awready_gap_min/max`  | `random` 模式下 AWREADY 间隔范围                 |

## 其他命令

| 命令              | 说明                                     |
| --------------- | -------------------------------------- |
| `make clean`    | 删除并重新创建 `bin/` 工作目录                    |
| `make all`      | 依次执行 `make clean com run`              |
| `make cdns_com` | 使用 Xcelium/xrun elaboration 编译         |
| `make sim`      | 使用 Xcelium/xrun GUI 模式启动仿真             |
