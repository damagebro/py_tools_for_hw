# gen_rtl_dummy

`gen_rtl_dummy` 从 RTL 源文件中提取 module、parameter 和 port，生成相同 module 名称的挖空 RTL。输入 RTL 可以使用绝对路径或相对当前执行目录的相对路径。

## 使用方式

```bash
python -B src/gen_rtl_dummy.py C:/abs/path/to/source.sv
```

在工具目录中，也可以直接使用相对路径：

```bash
python -B src/gen_rtl_dummy.py test/sample_rtl.sv
```

默认生成 `dummy.sv`，默认模式是 `bbox`。可通过 `-o` 指定输出文件：

```bash
python -B src/gen_rtl_dummy.py C:/abs/path/to/source.sv -o out_dummy.sv
```

## 挖空模式

| mode                    | 输出行为                                                         |
| ----------------------- | ------------------------------------------------------------ |
| `bbox`                  | 保留端口方向，所有普通 output 用 `assign` tie 为 `'0`                     |
| `stub`                  | 只保留 module/parameter/port 声明，不生成内部逻辑                         |
| `port_swap`             | input 改为 output、output 改为 input；`i_`/`o_` 名称同步互换             |

示例：

```bash
python -B src/gen_rtl_dummy.py C:/abs/path/to/source.sv -m stub -o source_stub.sv
python -B src/gen_rtl_dummy.py C:/abs/path/to/source.sv -m port_swap -o source_port_swap.sv
```

## 说明

- 支持 ANSI/非 ANSI Verilog 端口，以及 SystemVerilog packed/unpacked array、package type、struct/union/enum 和 interface/modport 风格端口。
- `bbox` 只对普通 output 生成 tie-off；interface/modport 和 inout 端口按原样保留。
- `port_swap` 只交换普通 input/output；inout、interface/modport 端口保持不变。
- 输出 module 名称与原 RTL 一致，因此应在替换原模块时使用，避免和原 RTL 一起编译造成重复定义。
