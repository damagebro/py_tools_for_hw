# gen_rtl_inst

`gen_rtl_inst` 用于从一个 Verilog/SystemVerilog RTL 文件中提取模块信息，并生成 RTL 集成例化代码片段。

## 使用方式

```bash
python -B src/gen_rtl_inst.py C:/abs/path/to/rtl.sv
```

默认输出：

```text
inst.sv
```

也可以指定输出文件：

```bash
python -B src/gen_rtl_inst.py C:/abs/path/to/rtl.sv -o out_inst.sv
```

需要把例化片段直接交给编辑器或其他脚本时，使用 `--stdout`，此时不生成 `inst.sv`：

```bash
python -B src/gen_rtl_inst.py C:/abs/path/to/rtl.sv --stdout
```

## 功能说明

- 提取 `module`、端口参数列表中的 `parameter`，以及 module 内部声明的 `parameter`。
- 不提取 `localparam`。
- 支持 ANSI 和非 ANSI Verilog 端口声明。
- 支持 SystemVerilog packed array、unpacked array、package type、struct/union/enum type 和 interface/modport 风格端口。
- 生成 signal declare、input assign 和显式 `.port(signal)` 例化连接。
- 例化信号名使用 `u_inst_[i|o|io|if]_<port_name>`，原端口已有 `i_`/`o_` 前缀时不会重复添加。
- input 端口名为 `clk`、`rst_n`，或以 `_clk`、`_rst_n` 结尾时，直接连接原端口信号，不额外生成 instance wire 和 assign。

## 输出结构

生成的 `inst.sv` 主要包含三段：

```text
//signal declare
//input assign
//instance
```

其中 input assign 只给普通 input 端口生成，`clk/rst_n/*_clk/*_rst_n` 会在 instance 中直接连接。
