# sim_ahb_vip

本目录基于 `gen_tb_demo` 的仿真环境骨架，提供 `ahb_interface` 和 `ahb_master`。默认 `top.sv` 内置一个零等待 AHB-Lite 应答模型，master 完成配置的 AHB 单拍传输后打印 `AHB VIP PASS`。

## 目录文件

| 文件                    | 说明                                        |
| --------------------- | ----------------------------------------- |
| `ENV.sh`              | 初始化 `SIM_DIR` 和仿真工作目录                     |
| `Makefile`            | VCS/Xcelium 常用仿真命令入口                      |
| `ahb_vip.cfg`         | AHB master 激励配置                           |
| `ahb_master.txt`      | `data_mode=txt` 的地址/数据写激励样例               |
| `rtl.f`               | DUT RTL filelist                          |
| `testbench.f`         | AHB testbench filelist                    |
| `tb/ahb_vip_pkg.sv`   | 配置文件解析函数                                  |
| `tb/ahb_interface.sv` | AHB-Lite interface 和 master/slave modport |
| `tb/ahb_master.sv`    | AHB 单拍激励                                  |
| `tb/top.sv`           | 顶层时钟、复位和默认应答模型                            |

## 常用命令

| 命令                            | 说明                             |
| ----------------------------- | ------------------------------ |
| `make com`                    | 使用 VCS 编译 RTL 和 testbench      |
| `make run`                    | 使用默认 `ahb_vip.cfg` 运行          |
| `make run AHB_CFG=../my.cfg`  | 指定 AHB 配置文件运行                  |
| `make verdi`                  | 使用 Verdi 查看波形和源代码              |

## 激励配置

配置文件使用 `m0.` 前缀，常用字段如下：

| 配置项                       | 说明                                        |
| ------------------------- | ----------------------------------------- |
| `m0.enable`               | 是否启用 master                               |
| `m0.base_addr`            | 起始地址                                      |
| `m0.byte_size`            | 传输字节数，按 AHB 数据宽度向上取整                      |
| `m0.rw_mode`              | `write`、`read` 或 `write_read`             |
| `m0.data_mode`            | `addr`/`data=addr`、`file`、`txt` 或常量模式     |
| `m0.data_value`           | 常量模式使用的数据                                 |
| `m0.data_file`            | `file` 的二进制数据文件或 `txt` 的事务文件              |
| `m0.hsize`                | AHB `HSIZE`，默认按总线字节数自动设置                  |

`data=addr` 会让每个字节使用当前地址的低 8 位，便于波形和 memory 内容检查。真实 DUT 接入时，将 `top.sv` 中的默认应答替换为 DUT 连接。

`data_mode=txt` 时，`ahb_master` 忽略 `base_addr`、`byte_size` 和 `rw_mode`，按 `data_file` 中的 `addr data` 对顺序逐笔发起 AHB 写传输；空白、空行和 `#` 之后的注释均会忽略。`data_file` 路径相对仿真运行目录 `bin/`，可直接使用 `ahb_master.txt`：

```ini
m0.data_mode=txt
m0.data_file=../ahb_master.txt
```

```text
0x00001000 0x12345678   # addr data
0x00001004 0x1
0x00001008 0x2
```

## 其他命令

| 命令                   | 说明                                        |
| -------------------- | ----------------------------------------- |
| `make clean`         | 删除并重新创建 `bin/` 工作目录                       |
| `make all`           | 依次执行 `make clean com run`                 |
| `make cdns_com`      | 使用 Xcelium/xrun elaboration 编译            |
| `make sim`           | 使用 Xcelium/xrun GUI 启动仿真                  |
