# sim_axi_vip

`sim_axi_vip` 基于 `gen_tb_demo` 目录结构构建。环境支持 `N 个 axi_master -> axi_arbiter -> 1 个 axi_slave`，所有 master 访问同一份 slave memory，不再生成 N 组彼此独立的 master/slave 一对一连接。

## 目录文件

| 文件                    | 说明                                        |
| --------------------- | ----------------------------------------- |
| `ENV.sh`              | 仿真环境变量和 `SIM_DIR` 初始化脚本                   |
| `Makefile`            | VCS/Xrun 常用仿真命令入口                         |
| `axi_vip.cfg`         | 多 master 和共享 slave 的运行配置                  |
| `rtl.f`               | DUT RTL filelist，默认为空                     |
| `testbench.f`         | AXI VIP testbench filelist                |
| `tb/axi_interface.sv` | AXI interface 和 master/slave modport      |
| `tb/axi_master.sv`    | 可配置 AXI master 激励                         |
| `tb/axi_arbiter.sv`   | AW/W/B、AR/R 通道轮询仲裁和 response 路由           |
| `tb/axi_slave.sv`     | 单个共享 AXI slave memory                     |
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
| `master_num`    | 默认启用的 master 数量                           |
| `timeout_cycle` | top 等待全部 master done 的周期数                 |

master 使用 `mN.` 前缀，`N` 从 0 开始；共享 slave 只使用 `s0.` 前缀。

master 配置：

| 配置项                           | 说明                                        |
| ----------------------------- | ----------------------------------------- |
| `mN.enable`                   | 是否启用该 master                              |
| `mN.base_addr`                | 写事务起始地址                                   |
| `mN.byte_size`                | 写入数据总 byte 数                              |
| `mN.data_mode`                | `addr`/`data=addr`、`file` 或常量模式           |
| `mN.data_value`               | 常量数据模式使用的默认数据                             |
| `mN.data_file`                | `data_mode=file` 时读取的二进制文件                |
| `mN.axi_awvalid_mode`         | `continuous` 或 `random`                   |
| `mN.axi_awvalid_gap_min/max`  | `random` 模式下 AWVALID 间隔范围                 |

共享 slave 配置：

| 配置项                           | 说明                                        |
| ----------------------------- | ----------------------------------------- |
| `s0.enable`                   | 是否启用共享 slave                              |
| `s0.mem_size`                 | 共享 slave memory byte 容量                   |
| `s0.data_mode`                | `addr`/`data=addr`、`file` 或常量模式           |
| `s0.data_value`               | 常量初始化模式使用的默认数据                            |
| `s0.data_file`                | `data_mode=file` 时初始化 memory 的文件          |
| `s0.axi_reorder_depth`        | B response 乱序窗口；`0` 表示不乱序                 |
| `s0.axi_awready_mode`         | `continuous` 或 `random`                   |
| `s0.axi_awready_gap_min/max`  | `random` 模式下 AWREADY 间隔范围                 |

## 多 Master 连接

设置 `master_num=N` 并增加 `m0` 到 `mN-1` 的配置后，所有已启用 master 会经 `axi_arbiter` 访问同一个 `s0`。仲裁器对 AW 和 AR 使用轮询选择；AW 被接受后会锁定对应 master，直到 WLAST 握手完成，B response 再根据该 master 的固定 AXI ID 路由返回。`top.sv` 默认预留 `MAX_AXI_MASTER_NUM=8`，且该值不得超过 `2 ** AXI_IDW`。

例如启用两个 master：

```ini
master_num=2
m0.base_addr=0x00001000
m1.base_addr=0x00002000
s0.mem_size=0x00004000
```

## 其他命令

| 命令              | 说明                                     |
| --------------- | -------------------------------------- |
| `make clean`    | 删除并重新创建 `bin/` 工作目录                    |
| `make all`      | 依次执行 `make clean com run`              |
| `make cdns_com` | 使用 Xcelium/xrun elaboration 编译         |
| `make sim`      | 使用 Xcelium/xrun GUI 模式启动仿真             |
