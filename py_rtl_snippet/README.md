# py_rtl_snippet

`py_rtl_snippet` 是一套可复用的 SystemVerilog 代码片段库。人工维护的源文件是 Markdown，脚本将其解析为 VS Code 原生 `.code-snippets` JSON。导入后的片段展开不依赖 Python、`hw_tool` 或当前 workspace，适合日常 RTL 编辑时直接使用。

## 设计目标

片段遵循 `doc/coding_style.md` 中的主要约定：模块名和信号名使用小写，参数名使用大写，默认时钟/复位信号为 `clk`/`rst_n`，RTL 注释使用英文，时序与组合逻辑使用 `always @`，端口和连接信号使用明确的方向语义。

当前片段分为两类：

| 分类         | 内容范围                                                            |
| ------------ | ------------------------------------------------------------------- |
| RTL 语句片段 | 模块头、时序/组合逻辑、DFF、struct、union、enum。                   |
| 总线端口片段 | Valid-ready、RAM、CSR、eBus、APB、AXI4 的 `input/output` 端口组。  |

总线片段不生成 `interface` 或 `modport`，可直接插入 module 的端口列表。时钟与复位通常已经由 `rtl-module` 提供，因此总线片段只列出协议自身的数据信号和握手信号。

## 快速使用

人工维护 [rtl_snippets.md](input/rtl_snippets.md)，再生成可直接导入 VS Code 的 [systemverilog.code-snippets](snippets/systemverilog.code-snippets)：

```bash
python -B src/py_rtl_snippet.py -o snippets/systemverilog.code-snippets
```

在 VS Code 中执行 `Snippets: Configure Snippets`，新建一个全局 snippets 文件，再将生成的 JSON 内容复制进去。当前 scope 为 `systemverilog,verilog`；仅当安装的 HDL 扩展使用其他 language identifier 时，才需要修改这个 scope。

需要使用 Tab 触发展开时，可在 VS Code 设置中加入：

```json
"editor.tabCompletion": "on"
```

在 SystemVerilog/Verilog 源文件中输入 `rtl-always_dff` 等前缀，从补全列表选择片段。插入后可反复按 Tab，在各个占位符之间跳转并修改内容。

## Markdown 格式

每个片段以 `## <prefix>` 开始；其下可选填写 `title`、`description`、`scope`，并放入一个 `systemverilog` 代码块。直接编辑代码块后重新运行生成命令即可。

````markdown
## rtl-example

- title: RTL example
- description: Example snippet.
- scope: systemverilog,verilog

```systemverilog
assign ${1:o_data} = ${2:i_data};${0}
```
````

## 常用前缀

| 前缀                         | 说明                                         |
| ---------------------------- | -------------------------------------------- |
| `rtl-module`                 | 含参数、对齐端口和代码分区注释的模块头。     |
| `rtl-always_dff_no_rst`      | 无复位的 `always @(posedge clk)` 时序块。    |
| `rtl-always_dff`             | 低有效异步复位 DFF，单行条件赋值。           |
| `rtl-always_dff_begin_end`   | 低有效异步复位 DFF，分支带 `begin/end`。     |
| `rtl-always_comb`            | `always @*` 组合逻辑块。                     |
| `rtl-struct`                 | packed struct typedef，类型名使用 `_ts`。    |
| `rtl-union`                  | packed union typedef，类型名使用 `_tu`。     |
| `rtl-enum`                   | enum typedef，类型名使用 `_te`。             |
| `rtl-vld_rdy`                | Valid-ready 收发端口组。                      |
| `rtl-ram_port`               | 单端口 RAM 请求/响应端口组。                  |
| `rtl-csr_port`               | CSR 请求/响应端口组。                         |
| `rtl-ebus_rdport`            | eBus 读请求/响应端口组。                      |
| `rtl-ebus_wrport`            | eBus 写请求/响应端口组。                      |
| `rtl-apb_port`               | APB slave 端口组。                            |
| `rtl-axi4_port`              | AXI4 slave 五通道端口组。                     |

## 命令行工具

命令行工具解析 Markdown，并生成版本受控的 VS Code snippets 文件或预览 RTL。这样 VS Code 插件后续也能复用同一份片段内容。

```bash
python -B src/py_rtl_snippet.py --list
python -B src/py_rtl_snippet.py --print
python -B src/py_rtl_snippet.py -o out/systemverilog.code-snippets
python -B src/py_rtl_snippet.py --preview out/py_rtl_snippet_preview.sv
python -B src/py_rtl_snippet.py -i path/to/custom_snippets.md -o out/custom.code-snippets
```

`-i` 指定人工维护的 Markdown 输入，默认是 `input/rtl_snippets.md`。`-o` 会在需要时创建父目录，并以 UTF-8 写入生成的 JSON。

`--preview` 将所有片段按默认占位符展开为一个 `.sv` 文件，用于人工检查。时序/组合逻辑片段保持纯 `always` 块，总线片段保持纯参数和端口声明，均不额外包裹 module。因此该文件仅是片段预览，不应加入实际 RTL filelist 或作为完整 RTL 编译。

## 验证

```bash
python -B test/test_py_rtl_snippet.py
```
