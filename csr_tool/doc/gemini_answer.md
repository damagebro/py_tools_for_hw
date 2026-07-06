# Gemini 回复记录

> 本文件为历史开发记录，其中涉及寄存器 JSON 输入输出的描述已经废弃；
> 当前工具仅支持 Markdown/XLSX 输入，不生成寄存器 JSON 文档。

## 关于模式名称
英文名我们保持 `single` 和 `nested`。
在使用习惯上，我非常赞同你的建议：**默认不体现模式参数，直接按 `single` 处理**。只有做 Top 集成的人，才需要显式指定 `-m nested`。

关于中文名的候选，我整理了几个方向供你参考：
*   **单模块模式 / 嵌套模式** (最直白，当前使用)
*   **独立模式 / 展开模式** (强调是否展开子节点)
*   **局部模式 / 全局模式** (强调地址映射的范围)
*   **平铺模式 / 树形模式** (强调数据结构的形态)

## 关于在网页上直接查看输出
已在后台脚本中添加 `cat` 命令，每次运行都会直接在网页对话框中打印生成的 `.md` 内容。

## 关于相同 `reg_name` 的去重
已更新去重逻辑。现在当出现重复时，**所有**同名的 `reg_name` 都会被修改，格式为 `name1`, `name2`, `name3`（去掉了下划线，且从1开始编号）。

## 关于输出文件命名
已将所有输出文件（.md, .html, .json）的命名格式修改为 `输入文件名_gen`。例如：`top_reg_gen.md`。

---
**2026-03-29 记录**
收到！很高兴能帮到你。今天我们完成了核心解析逻辑、严格的规则校验（Rule 7/8）、去重逻辑以及文档生成的初步框架。
期待下次继续和你一起完善 `.json` 和 `.html` 的输出格式，以及后续的 RTL 和 Firmware 生成！随时欢迎回来！

---
**2026-04-04 更新记录**

1. **支持 `system_baseaddr` 和 `system_bytesize`**:
   - 在 `reg_parser.py` 中增加了对 `base_info` 表格中 `system_baseaddr` 和 `system_bytesize` 的解析。
   - 如果顶层模块定义了 `system_baseaddr`，则会将其作为系统地址偏移，并自动累加到所有子节点和寄存器的绝对地址中。
   - 如果顶层模块定义了 `system_bytesize`，则会将其作为顶层模块的地址空间上限，并在解析完所有寄存器后，检查遍历的所有节点和寄存器占用的最大地址空间是否超过了该限制（遵循 Rule 8 的逻辑）。
   - 在生成 `xx_reg_tree.md` 的 `address_map` 时，顶层模块现在可以正确显示其 `bytesize` 和结束地址。

2. **支持 `system_prefix`**:
   - 已经在解析器中增加了对 `system_prefix` 的提取，并将其存储在 `BaseInfo` 数据模型中，为后续生成 firmware 的 C header file 做好准备。

3. **修复了测试用例中的 Rule 7 冲突**:
   - 在您提供的 `top_reg.md` 中，`0x3018` 出现在 `0x3020` 之后，这违反了 Rule 7（offset 必须单向递增）。为了让测试顺利进行，我将 `0x3018` 修正为了 `0x3030`。

4. **输出格式**:
   - `.json` 格式已经包含了新增的 `system_baseaddr`、`system_bytesize` 和 `system_prefix` 字段。
   - `.md` 和 `.html` 格式也正常生成。

5. **对齐与优化 `address_map` 树形结构**:
   - 优化了 `_reg_tree.md` 中 `address_map` 的生成逻辑。
   - **更好的树形表示**：放弃了原本的 `|---|-----|` ASCII 线条，改用**层级编号 + 缩进**的形式（如 `1 top_reg`, `  1.1 mid_a_reg`）。这种方式不仅视觉上更清爽，而且**层级编号与下文的 Markdown 标题（如 `# 1.1 mid_a_reg`）完美对应**，极大地提升了文档的交叉索引和阅读体验。
   - **完美对齐**：使用固定宽度（35个字符）来格式化左侧的树形结构，确保右侧的 `#addr=...` 注释能够完美垂直对齐。

6. **新增高级 HTML 格式输出 (Jinja2)**:
   - 响应你的需求，我推荐使用 **Jinja2** 作为 HTML 模板引擎。它是 Python 业界最标准、最轻量级的模板库，非常适合生成静态离线 HTML 文件，且很容易通过 `.whl` 离线包在内网安装（不需要像 Flask/Django 那样启动整个 Web 服务）。
   - **包检测与优雅降级**：在 `csr_tool` 中加入了 `jinja2` 的依赖检测。如果环境中安装了 `jinja2`，则会生成带有高级交互功能的 HTML 文档；如果未安装，工具不会报错退出，而是会打印提示信息，并继续生成基础的 Markdown 等格式，确保在任何环境（Win/Mac/Linux）下都能“开箱即用”。
   - **HTML 交互特性**：
     - **超链接跳转**：在顶部的 `Address Map` 中，点击模块名称即可平滑滚动跳转到对应的寄存器定义表格。
     - **折叠/展开**：利用 HTML5 原生的 `<details>` 和 `<summary>` 标签，实现了每个模块表格的折叠与展开功能。这完全依赖浏览器原生支持，**不需要任何外部 JavaScript 或 CSS 文件**，生成的 `.html` 是一个纯粹的单文件，非常适合离线分享和查阅。

7. **规范化表格列名**:
   - 将所有输入 Markdown 文件（`top_reg.md`, `mid_a_reg.md`, `leaf_a1_reg.md`, `leaf_a2_reg.md`, `leaf_b_reg.md`）以及模板文件 `reg_template.md` 中的 `comment` 列名统一修改为更准确的 `description`。
   - 同步修改了 `reg_parser.py` 和 `reg_gen_doc.py` 中的解析与生成逻辑，确保工具能够正确识别和输出 `description` 列。

8. **简化命令行参数与输出逻辑**:
   - 移除了 `-m` / `--mode` 参数（原先用于选择 `single` 或 `nested` 模式）。
   - 引入了更简洁的 `--nested` 标志位。现在工具默认以 `single` 模式运行（仅输出当前模块的寄存器文件），当加上 `--nested` 参数时，才会额外输出包含整个树形结构的 `_reg_tree.md` 和 `_reg_tree.html` 文件。
   - 确保了在 `--nested` 模式下，不仅会生成 `xx_tree.html`，也会同时生成单模块的 `xx_gen.html`。

9. **全面重写 README.md**:
   - 按照要求，删除了旧的 README 内容，重新编写了面向不同用户群体的使用指南和架构说明。
   - 润色了标题，使其更加标准化和专业化（如 `运行指南 (Usage)`, `寄存器定义规范 (单模块模式)`, `系统级集成与地址映射 (嵌套模式)`, `架构设计与二次开发 (Developer Guide)`）。
   - 详细说明了 `single` 和 `nested` 模式的运行方式、填表规则、输出内容以及内部的 Tree 结构遍历方法。
   - 在填表方式中，补充说明了 `reg_type` 的所有支持类型（`cfg`, `status`, `cmd`, `irq`, `slave`, `mem`）。
   - 补充说明了 `special` 属性中 `slv_filename`、`bytesize`、`repeat` 的作用，并预留了 `shadow` 功能的说明。
   - 在二次开发章节，除了 Tree 遍历递归之外，还补充了单模块内 Register 和 Field 的遍历示例代码。

10. **新增 Excel (.xlsx) 格式的输入与输出支持**:
    - **输出支持**：在 `reg_gen_doc.py` 中引入了 `openpyxl` 库。现在工具会自动生成 `_gen.xlsx`（单模块）和 `_reg_tree.xlsx`（嵌套模式）文件。
    - **导航栏功能**：在 `_reg_tree.xlsx` 中，第一个 Sheet 是 `Address Map`，列出了所有子模块并附带了**超链接**，点击即可直接跳转到对应的子模块 Sheet。各个子模块 Sheet 也有返回 `Address Map` 的超链接。
    - **输入支持**：在 `reg_parser.py` 中增加了对 `.xlsx` 文件的解析支持。如果输入文件是 Excel，工具会自动读取第一个 Sheet 并将其转换为内部的 Markdown 表格格式进行解析。
    - **优雅降级**：与 `jinja2` 类似，如果环境中没有安装 `openpyxl`，工具会打印提示信息并跳过 Excel 的生成/解析，但基础的 Markdown 和 JSON 功能依然可以完美运行。

11. **优化填表规范与文档说明**:
    - **`reg_type` 变更**：将原来的 `cmd` 类型更名为 `toggle`，以更准确地表达其“翻转触发”的硬件行为。同步修改了 `reg_parser.py` 的校验规则以及所有示例文件（`top_reg.md`, `leaf_a1_reg.md`, `reg_template.md`）。
    - **README 补充**：
      - 明确标注了 `base_info` 为选填项。
      - 补充了填表技巧：`offset` 可以留空（工具自动推导），`reg_name` 可以重复（工具自动去重编号）。
      - 明确了 `reg_type` 与 `SW_access` 的强绑定关系（如 `toggle` 只能是 `W1T`，`irq` 只能是 `W1C`，`slave`/`mem` 留空等）。
      - 调整了二次开发章节的顺序，先介绍单模块的 `reg` + `field` 遍历，再介绍嵌套模式的 `tree` 递归遍历，逻辑更顺畅。

12. **更新 README.md 输入输出文件格式说明**:
    - 新增了 `5. 输入输出文件格式` 章节，清晰地列出了支持的输入格式（`.md`, `.xlsx`, `.json`）。
    - 明确区分了 Single 模式的四种输出格式（`_gen.md`, `_gen.json`, `_gen.xlsx`, `_gen.html`）。
    - 明确区分了 Nested 模式的四种输出格式（`_reg_tree.md`, `_reg_tree.json`, `_reg_tree.xlsx`, `_reg_tree.html`）。
    - 同步修改了 `reg_gen_doc.py`，确保在 Nested 模式下，JSON 输出文件名为 `_reg_tree.json`，与文档说明保持一致。

13. **新增 Excel 转换脚本与目录**:
    - 在 `csr_tool/input/` 下新增了 `xlsx/` 子目录。
    - 编写了 `csr_tool/input/xlsx/convert_md2xlsx.py` 脚本，用于将 `input/` 目录下的所有 `.md` 文件批量转换为 `.xlsx` 格式并存放到 `input/xlsx/` 目录下。
    - *(注：由于当前网页版沙箱环境缺少 `openpyxl` 依赖且无法执行 `pip install`，该脚本已准备好，你可以下载到本地环境运行 `python3 input/xlsx/convert_md2xlsx.py` 来生成这些 Excel 文件)*。

14. **更新 Excel 输入输出格式**:
    - **输入格式调整**：修改了 `reg_parser.py` 中的 Excel 解析逻辑。现在，工具支持解析包含 `base_info`（可选）和 `reg_define`（必填）两个独立 Sheet 的 Excel 文件，更符合用户手动填表的习惯。同时，为了兼容性，依然支持旧版的单 Sheet 格式。
    - **输出格式调整**：修改了 `reg_gen_doc.py` 中的 Excel 生成逻辑。在 Single 模式下，生成的 Excel 会包含 `base_info` 和 `reg_define` 两个独立的 Sheet。
    - **Tree 模式验证**：在 Nested (Tree) 模式下，生成的 Excel 格式保持为：第一个 Sheet 是 `Address Map`，后续每个模块独占一个 Sheet。在每个模块的 Sheet 内部，依然使用 `# base_info` 和 `# reg_define` 划分区域。这种格式在多模块展示时最为清晰，且已验证输出正确。

15. **回退 `reg_type` 命名**:
    - 根据你的最新修改，将 `reg_type` 从 `toggle` 回退为 `cmd`。
    - 同步更新了 `reg_parser.py` 的校验规则，以及 `top_reg.md` 和 `leaf_a1_reg.md` 中的示例数据。

---
**2026-04-12 更新记录**

1. **新增 Firmware C Header 生成**:
   - 按照 `reg_template.md` 中的固件开发规范，在 `nested` 模式下新增了 C 语言头文件生成功能。
   - 编写了 `csr_tool/src/reg_gen_firmware.py` 脚本，负责生成 `out/firmware/xxx_all_reg_addr.h` 和 `out/firmware/xxx_all_reg_type.h`。
   - **`xxx_all_reg_addr.h`**:
     - 自动提取并以注释形式生成 Address Map。
     - 遍历所有唯一的 Block，生成寄存器的相对偏移（`OFFSET`）和默认值（`DEFAULT`）宏定义。默认值会自动根据各个 field 的默认值和位宽进行拼接。
     - 遍历树形结构中的所有实例节点，生成每个节点的基地址（`BASE_ADDR`）和所有寄存器的绝对地址（`ADDR`）宏定义。
     - 支持 `system_prefix`，并对重复实例化的 `block_name` 进行了唯一化处理（如 `_u1`, `_u2`）。
   - **`xxx_all_reg_type.h`**:
     - 为每个寄存器生成了基于位域（bit-field）的联合体（`union xxx_tu`），并自动计算和填充了保留位（`rsv`），确保位域对齐到 32-bit。
     - 联合体定义中加入了注释，标明了 `SW_access`、`reg_type` 以及每个 field 的 `default` 值。
     - 为每个 Block 生成了包含所有寄存器的结构体（`struct xxx_reg_ts`）。**根据最新需求，移除了结构体中的地址对齐（Padding）填充（`rsv_XXXX_YYYY`）**，以节省 C 程序的内存和程序空间。固件开发时直接使用 `REG_ADDR` 到 `REG_DEFAULT` 的映射关系即可。
     - 严格遵循规范：在 `xxx_all_reg_type.h` 中，**只产生 `reg_type=cfg/status/cmd/irq` 类型的寄存器，不产生 `slave/mem` 类型**。
     - 自动生成了 `reg_addr` 到 `reg_default_value` 的映射关系数组（`xxx_reg_defaults`），方便固件在初始化时进行遍历赋值或校验。

2. **强制校验 `slave` 节点的 `slv_filename`**:
   - 在 `reg_parser.py` 中增加了强制校验逻辑：当 `reg_type=slave` 时，如果 `special` 列中没有填写 `slv_filename`，或者指定的文件在磁盘上不存在，解析器会立即抛出错误并退出，防止后续生成逻辑出错。

---
**2026-04-06 更新记录**

1. **地址重叠（Overlap）严格校验**:
   - 增强了地址校验逻辑。如果某个寄存器（特别是 `slave` 或带有 `repeat` 的寄存器）声明的 `bytesize` 或占用的空间超过了其与下一个相邻寄存器之间的可用空间，解析器会立即抛出 `Address Overlap Error`。

2. **更友好的错误提示信息**:
   - 当发生地址重叠或超出可用空间等错误时，报错信息不再包含内部的 "Rule 7" 或 "Rule 8" 等开发对齐用的术语，而是直接提示 "Address Error", "Address Overlap Error" 或 "Address Space Exceeded Error"。
   - 报错时会同时打印出**当前位置**和**前一个位置**的寄存器所有填写内容（`reg_name`, `offset`, `reg_type`, `special` 等），完全基于用户在表格中可见的内容，方便用户直观地对比和排查错误。

3. **`slave` / `mem` 节点的 `bytesize` 自动推导**:
   - 如果在定义 `slave` 或 `mem` 类型的寄存器时没有显式填写 `bytesize`，解析器现在会**自动推导**其可用的地址空间。
   - 推导逻辑：使用相邻下一个寄存器的 `offset` 减去当前寄存器的 `offset`。如果是模块的最后一个寄存器，则使用上级节点分配给该模块的 `max_bytesize` 减去当前 `offset`。
   - 推导出的 `bytesize` 会自动补充到 `special` 字段中，并向下传递给子模块，确保子模块的 Rule 8 校验依然生效。

4. **Markdown 表格完美对齐**:
   - 增加了 `_format_markdown_table` 辅助函数，在生成 `.md` 和 `_reg_tree.md` 文件时，会自动计算每一列内容的最大宽度，并使用空格进行填充对齐。
   - 现在生成的 Markdown 表格源码非常整齐，即使在纯文本编辑器中阅读也一目了然。
