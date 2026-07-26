# py_sim

`gen_tb.py`用于生成和`templates/sim`同结构的独立仿真环境，便于脚本自动创建临时testbench。

常用命令：

```bash
python3 gen_tb.py -o build/sim -top top_module -f '$PROJ_RTL/rtl.f' -e PROJ_RTL=C:/proj
```

参数说明：

| 参数                   | 说明                                                      |
| ---------------------- | --------------------------------------------------------- |
| `-o/--output`          | 输出仿真目录，默认`./sim`                                 |
| `-top/-t/--top_module` | 在`tb/top.sv`中例化的DUT top module                       |
| `-f/--filelist`        | 写入`rtl.f`的项目filelist                                 |
| `-e/--sim_env`         | 写入`ENV.sh`的环境变量，格式为`NAME=VALUE`，可重复指定    |
| `-s/--env-shell`       | `ENV.sh`语法风格，可选`sh`或`csh`，默认`sh`               |

生成后的环境只依赖`SIM_DIR`和通过`-e`写入的环境变量；默认`rtl.f`不额外引用任何RTL。生成目录内会同步生成`README.md`，说明`make com/run/verdi/cdns_com/sim`等常用命令。
