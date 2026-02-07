==========================================================
AMBA RTL Generator Tool (SOC Interconnect Edition)
==========================================================

1. 项目目录结构
----------------------------------------------------------
gen_amba/
├── cfg/
│   ├── template.txt           # 协议模板 (支持角色定义 [label:role])
│   └── template_mini.txt      # 备选模板
├── src/
│   └── gen_amba.py            # 核心生成脚本
├── out/                       # 自动生成的输出目录
│   └── amba_top.sv            # 生成的 SystemVerilog 顶层文件
└── config.json                # 全局配置文件 (前台输入)

2. 核心功能特性
----------------------------------------------------------
- 像素级风格还原:
    * 完美还原模板中信号名与逗号之间的“空格距离”。
    * 支持 wire, logic, reg 等各种声明类型的动态纵向对齐。
- 前缀内循环生成 (Intra-Prefix Loop):
    * 当 mode 设置为交替模式时，脚本会针对每一个 prefix 连续生成 Master 和 Slave 两组接口。
- 双下划线前缀翻转 (Prefix Flip):
    * 识别 prefix 中的 "__" 分隔符。
    * 在交替生成的第二组信号中，自动将 "A__B" 翻转为 "B__A"，符合 P2P 互联命名规范。
- 智能模式切换 (Alternating Mode):
    * m_s_alt: 对每个前缀，先生成 Master 信号，再生成 Slave 信号。
    * s_m_alt: 对每个前缀，先生成 Slave 信号，再生成 Master 信号。
- 后台角色判定 (Role-based):
    * 模板头支持 [protocol:M] 或 [protocol:S] 标注。
    * 脚本根据 (当前生成角色 + 后台信号组角色) 自动计算 input/output 的镜像翻转。

3. 配置指南 (config.json)
----------------------------------------------------------
- template_file: 指定使用的模板文件名。
- prefix: 支持字符串数组，如 ["cpu__sbf", "sbf__mem"]。
- mode: 支持 master, slave, m_s_alt, s_m_alt。
- params: 提供位宽参数，支持数学表达式自动计算。

4. 运行说明
----------------------------------------------------------
- 执行命令: python3 src/gen_amba.py
- 输出路径: 自动输出至 out/ 目录下的 .sv 文件。

5. 输出对齐示例
----------------------------------------------------------
    input  logic [31:0] cpu__sbf_awaddr  ,  // 原始前缀 Master
    ...
    output logic [31:0] sbf__cpu_awaddr  ,  // 自动翻转前缀 Slave

==========================================================