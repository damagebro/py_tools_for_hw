# base_info

| item         | type_input        | description |
| :----------- | :---------------- | ----------- |
| reg_bitwidth | 32                | -           |
| system_addr  | 0xf0000000        | -           |
| system_size  | 0x1000            | 16KiB       |
| author       | dmg               | -           |
| email        | dmg@sensetime.com | -           |

# reg_define

| offset | reg_name | field   | msb | lsb | SW_access | default_value | reg_type | special                                  | description |
| :----- | :------- | :------ | :-- | :-- | :-------- | :------------ | :------- | :--------------------------------------- | :---------- |
| 0x0    | ctrl     | signal1 | 15  | 0   | RW        | 0x0           | cfg      | -                                        |             |
|        | ctrl     | signal2 | 31  | 0   | RW        | 0xdeadbeef    | cfg      | -                                        |             |
| 0x40   | dbg      | signal1 | 15  | 0   | RO        |               | status   | -                                        |             |
|        |          | signal3 | 31  | 20  |           |               |          | -                                        |             |
|        | dbg      | signal2 | 31  | 0   | RO        |               | status   | -                                        |             |
|        | cmd      | start   | 0   | 0   | W1T       | 0x0           | cmd      | -                                        |             |
|        | irq      | info    | 31  | 0   | W1C       | 0x0           | irq      | -                                        |             |
| 0x1000 | slv1     |         |     |     |           |               | slave    | slv_filename=sub_node.md, bytesize=0x400 |             |
| 0x2000 | slv2     |         |     |     |           |               | mem      | bytesize=0x100                           |             |

# 填写说明

* reg_type内容

1. reg_type=cfg, 配置寄存器
2. reg_type=status, 状态寄存器
3. reg_type=cmd, 翻转寄存器, 用于软件向硬件发送命令, 硬件检测翻转产生1个脉冲, 让内部开始运行
4. reg_type=irq, 规范中断寄存器使用; 还有同位宽的cfg_irq_mask+cfg_irq_en信号配合; irq_en作用于中断产生前, 让irq_reg不会置位; irq_mask作用于中断产生后, irq_level = irq_reg & ~irq_mask, irq_reg虽然置位, 但不会产生irq_level通知软件, 不过软件读取irq_reg是可以读到对应bit已被置位.
5. reg_type=slave, 可以嵌套下一个节点的寄存器文档; 子节点addr_base=offset填写内容, addr_size=special填写内容;
6. reg_type=mem, 不会嵌套下一个节点, 是当前节点有一块sram的地址空间被软件可见; addr_base=offset填写内容, addr_size=special填写内容

* 一些规则和填写技巧

1. rule1: offset不填，交给脚本自动填充; 默认之前reg_offset+4byte(reg_bitwidht/8);
2. rule2: reg_name可以重名, 交给脚本去重(如果有重复字符串结尾补1,2,3编号);
3. rule3: 不同reg_name之间, filed可以重名; 因为reg_name去重后一定唯一化表示
4. rule4: 一个reg_name可以填多个filed信号, msb/lsb单向递增, 但在32bit(reg_bitwidht)以内;  相关寄存器属性(reg_name/reg_type/SW_access)等, 只在reg_name第一行填写, 其他行留空;
5. rule5: csr_tool输出的doc内容, 可以再次作为输入, 再次输入的输出, 应该得到相同rtl/tb/firmware/doc的结果;
6. rule6: 每个寄存器表格offset都从0x0开始偏移，  从上层节点或根节点看到的绝对地址， 由树形图逐个节点递归过程累加得到;
7. rule7: 每个offset单向递增, 若手动填写不是单向递增, 则报错退出;
8. rule8: reg_type=slave的子节点内容, 填写的offset总地址空间, 不能超过上一个节点给定的bytesize空间大小; 超过则报错;

* special填写内容

1. special是特殊规则描述, 多种特殊规则之间用逗号分隔符隔开;  常见特殊规则有, repeat N/shadow/shadow N; repeat是同一个reg_name重复出现N次, 占N个reg_addr;  shadow是多一个寄存器副本, shadow N是有N个寄存器副本;
2. reg_type=cfg/status/cmd/irq的时候, 可以填repeat/shadow;
3. reg_type=slave的时候, 要填下一个子模块节点的slv_filename=sub_node.md; 选填bytesize(推荐必填), 限定addr+size寄存器地址空间, 若没填写bytesize, 从当前reg_name+下一行reg_name, 可限定bytesize大小;
4. reg_type=mem的时候, 不用填slv_filename, 因为访问当前节点的sram地址空间, 没有下一个模块;  必填bytesize, 告诉sram地址空间大小有多少;
5. 关于repeat N, N个reg的默认值可以不同, 在default_val中用CSV逗号分隔符方式给出初始值, 如果分割后初始值数量小于N, 以最后一个初始值填充到N; 比如寄存器a[4], 填了repeat 4, 如果default=0,1;  则a[0]=0, a[1]=a[2]=a[3]=1;

# 目录结构

```bash
| csr_tool/ |
| --------- |doc/
| --- | --- | reg_template.md    #文档说明草稿;
| --- |src/
| --- | --- | autogen_reg.py   #csr_tool程序入口, 有单模块模式+嵌套模式, 单模块模式=输入1个手填寄存器表格, 输出rtl/testbench/doc需要的寄存器相关文件;  嵌套模式=输入1个手填寄存器表格, 输出rtl/testbench/doc/firmware需要的寄存器相关文件, 输出address_map, testbench/firmware都能体现address_map;
| --- | --- |reg_parser.py    #所有输入文件类型解析, 产生中间json格式的变量; 后续的步骤都通过json格式传参;  可以有多个reg_parser_xx.py文件, 对应不同输入文件类型, 或通用的解析函数定义;
| --- | --- |reg_gen_rtl.py
| --- | --- |reg_gen_tb.py
| --- | --- |reg_gen_doc.py
| --- | --- |reg_gen_firmware.py   #希望通过json2rtl/tb/doc/firmware等, 也请gemini选择更好的输出方式， 你好像推荐过jinja2模板?   到了reg_gen_other步骤我们再讨论;
| --- | input/    #所有手填寄存器输入文件
| --- |out/      #csr_tool输出内容, 输出rtl/testbench/doc/firmware, 对应下面几个输出目录;
| --- | --- | doc/  #输出的寄存器文件, (1)若是单模块模式, 可输出.xlsx/.html/.md/.json几种格式, 对应rule1~rule4填写简便的规则, 已被脚本自动处理, 输出是处理后的文档格式;  (2) 若是嵌套模式, 可输出.xlsx/.html等格式,  根据"树状图"结构产生多级标题, 给出address_map;
| --- | --- |rtl/  #待定
| --- | --- |tb/   #待定
| --- | --- |firmware/  #待定, 优先处理;
```

## 输入输出文件格式

1. .md格式, 如reg_template.md的内容, 有base_info + reg_define两个标题, 必须有reg_define, base_info可选;
2. .xlsx格式, base_info在sheet1, reg_define在sheet2, sheet_name就是base_info+reg_define;
3. .html格式, 当前主要作为输出格式, 不需要复杂的app交互代码, 调用简单的python产生离线html文件格式， 可以.html通过浏览器看到更好的格式呈现。
4. .json格式, 和中间变量内容一样, 方便查看;

## input目录中的module层级结构

```bash
|top/                  #addr=0x0000_0000~0x0000_ffff,  bytesize=0x10000;
|---|mid_a/            #addr=0x0000_1000~0x0000_17ff,  bytesize=0x0800;
|---|-----|leaf_a1     #addr=0x0000_1100~0x0000_113f,  bytesize=0x0040;
|---|-----|leaf_a2     #addr=0x0000_1200~0x0000_127f,  bytesize=0x0080;
|---|leaf_b/           #addr=0x0000_2000~0x0000_23ff,  bytesize=0x0400;
```

# 运行说明

1. python ./src/autogen_reg.py -i input/xx.md -o ./out/ (常规运行, 输出单个模块的rtl/tb/fw/doc相关寄存器文件)
2. python ./src/autogen_reg.py -i input/xx.md -m nested -o ./out/ (运行嵌套模式，当前模块节点是根节点, 展开所有子模块, 自动提取address_map和展开所有CSR寄存器定义 )

# 寄存器工具细节

按rtl设计/验证/固件开发等用户, 对生成的寄存器文件更多细节做描述

## csr_bus定义

csr_bus特点: 读写命令通道合并/读写数据通道分离/读写顺序和一致性保证/读写高性能+都支持超发;

```verilog
input  wire            csr_req_write  ,  //0=read, 1=write
input  wire [AW-1:0]   csr_req_addr   ,
input  wire [DW-1:0]   csr_req_wdata  ,
input  wire [DW/8-1:0] csr_req_wstrb  ,
input  wire            csr_req_valid  ,  //读写请求都可超发, 可以连续发valid;
input  wire            csr_req_ready  ,
output wire [DW-1:0]   csr_rsp_rdata  ,
output wire            csr_rsp_rvalid ,  //(1)读数据返回rvalid信号, 按请求顺序连续返回; (2)req_valid->rsp_rvalid的延时不固定, 由硬件实现决定;
```

csr_bus连续访问时序示例:

![csr_bus连续读写时序](assets/csr_bus_timing.png)

WaveDrom源文件: [csr_bus_timing.json](assets/csr_bus_timing.json)

## rtl开发

* 生成的rtl模块命名规范:
```verilog
1. 在输入reg_doc中, reg_name唯一化处理后叫做reg_name_unique, 一个reg_name里面有多个filed_name。 产生的端口信号命名方式是:
    - reg_type=cfg   ,  o_cfg_${reg_name_unique}_${filed_name}
    - reg_type=status,  i_sta_${reg_name_unique}_${filed_name}
    - reg_type=cmd   ,  o_cmd_${reg_name_unique}_${filed_name}
    - reg_type=irq   ,  i_irqsta_${reg_name_unique}_${filed_name} + o_irqclr_${reg_name_unique}_${filed_name};
    - reg_type=slave/mem,  tx_${csr_bus_interface}; //用端口数组把所有slave接口放一起, 不用参数化, 因为填表固定后, slave有多少个也固定了; 用注释给出slv_name, 比如: [0]=slv_name0, [1]=slv_name1;
    - 端口声明顺序, 除了reg_type=slave/mem放在端口列表最后, 其余寄存器按填表顺序；
2. 对于special属性的处理
    - special = repeat N, 端口用数组[N-1:0]表示;
    - special = shadow  , 端口增加 i_pulse_shadow_upen ;  //shadow 1和shadow等价, 可任意填写
    //csr_bus写shadow_reg, 读working_reg, i_pulse_shadow_upen由user_rtl产生, 让shadow_reg刷新到working_reg;
    - special = shadow N, 端口增加 i_pulse_shadow_upen+i_pulse_shadow_rden + o_dbg_shadow_wr_idx + o_dbg_shadow_rd_idx + o_dbg_shadow_water_level + o_pulse_err_write_when_full+o_pulse_err_read_when_empty;
    //shadown N且N>=2的时候, shadow_reg有一份, working_reg有N份; working[N]用fifo机制来更新i_pulse_shadow_upen=push_fifo, i_pulse_shadow_rden=pop_fifo;
    //o_dbg*把fifo状态拉出, 让用户决定是否上报;  o_dbg_shadow_water_level是fifo水线, 表示fifo还能装多少个数据, fifo为空时wl=N, fifo满的时候wl=0;
    //当shadow N>=2的时候, 多个reg的N必须相同, 否则shadow_fifo机制会出错。   但允许shadow N>=2和shadow 1同时存在;
    - shadow只对reg_type=cfg类型有效, 当有shadow时, 额外生成shadow_reg的dff, 命名方式: shadow_reg=r_shd_{reg_name_unique}_${filed_name};  working_reg(与当前一致, shadow N变成数组形式)=r_{reg_name_unique}_${filed_name};
3. 端口位宽声明, 除了CSR_AW/CSR_DW用参数化之外, 其他信号都是填表固定的, 用`output logic [3:0][31:0]`形式给出;
4. systemverilog/c语言关键字报错, 虽然rtl的信号名都是${reg_name_unique}_${filed_name}拼接, 但tb/firmware可能struct内只有filed_name, 对filed_name出现sv/c的关键字做检查，若出现直接报错并打印该reg所有信息。
```

* 生成的CSR内部对应的dff规范:
1. 一个reg_name_unique + 一个filed_name, 生成一个dff。 一个reg_name占一个always_ff代码块。
2. 当special = repeat N,  数组形式产生多个dff实体, 注意复位值可以各不相同;
3. 当special = shadow/shadow N的时候, TBD;

* reg_type=slave/mem的处理规范:
1. 虽然csr_bus读写都支持超发, 但不支持乱序，读写请求都只能顺序处理。
2. 对于csr_write, 只有csr_req_ready反压是否能接受写请求, 不需要写确认的状态; 所以无论多少个reg_type=slave组成的csr_demux逻辑, csr写请求都直接发出;
3. 对于csr_read, 需要csr_rsp_rvalid按正确顺序处理, csr_bus没有id标记请求顺序, 那么只能通过计数器(r_otf_cnt)记录请求完成情况。 当csr_read.req_valid往任一csr_demux输出接口或本地CSR寄存器的时候, r_otf_cnt+1; 收到csr_read.rsp_rvalid的时候, r_otf_cnt-1; 在csr_demux接口切换时, 若r_otf_cnt!=0, 一直反压csr_req_valid, 直到r_otf_cnt==0。 由此保证, csr_read请求顺序的正确性, 也保证了去往同一个csr_slave的读请求也可以超发。
4. r_otf_cnt位宽暂定8bit, 由`localparam CSR_REQ_OSD_NUM=256;`这个参数决定。 该参数不开放到module param_list, 只有非常熟悉csr_bus行为的用户, 可自行修改该参数。

* 画图直观展示reg_type=[cfg/status/cmd/irq]这几种类型dff在autogen_rtl模块内部或外部

![reg_type dff architecture](assets/reg_type_dff_arch.png)

* 画图直观展示shadow机制

<img alt="cfg shadow mechanism" src="./assets/cfg_shadow_mechanism.png" width="600">


## testbench开发

## firmware开发

仅在nested模式下, 生成给firmware使用的c_header_file; 有"xxx_all_reg_addr.h" + "xxx_all_reg_type.h"两大类文件;

- xxx_all_reg_addr.h: 定义寄存器地址映射, 给出每个寄存器的绝对地址和默认值;
- xxx_all_reg_type.h: 定义每个寄存器的结构体,  用struct/union和c语言位域实现;

一些固件c代码生成的细节说明:

1. 命名相关信息, 按system_name+block_name+reg_name三个拼接而成;
   - system_name: 来源与base_info中的system_prefix, 可选字段;  假设system_name=npu;
   - block_name: 来源寄存器定义文件的file_name, file_name=${block_name}[_reg|_register].md;  比如file_name=top_reg.md,  那么block_name=top;
   - reg_name: 来源与寄存器表格中的reg_name, 是一个**唯一化**的标识。
2. ${block_name}_all_reg_addr.h的文件内容:
   - a. address_map, 在nested模式已经提取出来, 在文件头部用注释给出;
   - b. 遍历nested递归找到的每个block, 生成每个block的寄存器offset地址+默认值;
     - (1)reg_offset_addr: #define ${BLOCK_NAME}_${REG_NAME}_OFFSET  0x??;
     - (2)reg_default_val: #define ${BLOCK_NAME}_${REG_NAME}_DEFAULT 0x??;  //default值要把reg_name中的所有filed默认值, 按所在bit_pos拼接为32bit的值。
     - (3)reg_bitwidth大多数情况都是32bit,  如果小于32bit也按32bit生成, 如果是64bit应该可以生成; 如果大于64bit则报错提示不支持。
   - block_name唯一化; 注意block_name可能会重复, 因为同一个block可能出现在"树形图"不同节点， 从rtl角度看, 是同一个module被实例化到了不同的hierachy; 我们要对block_name做唯一化, 方式是:
     - (1) 如果block_name在所有节点只出现一次, 则block_name不做任何处理;
     - (2) 如果block_name在所有节点出现多次, 则按先后顺序进行编号, unique_block_name = ${block_name}_u1, ${block_name}_u2; 按xx_u1/u2/u3进行编号, u解释为unique的缩写。
   - c. 按"树形图"顺序, 生成所有寄存器的绝对地址;
     - (1)生成每个节点的基地址: #define ${SYSTEM_NAME}_${UNIQUE_BLOCK_NAME}_BASE_ADDR 0x??;  //从address_map已提取到该基地址的值;
     - (2)在每个节点内, 生成每个寄存器的绝对地址: #define ${SYSTEM_NAME}_${UNIQUE_BLOCK_NAME}_${REG_NAME}_ADDR (${SYSTEM_NAME}_${UNIQUE_BLOCK_NAME}_BASE_ADDR + ${BLOCK_NAME}_${REG_NAME}_OFFSET);
3. ${block_name}_all_reg_type.h的文件内容:

```c
// typedef unsigned int u32;  //可以include一个c标准库,  好像有uint32_t, 寻找一个常见的库?
#include "xxx_all_reg_addr.h"  //导入所有寄存器地址+默认值;

//1. 遍历每个block, 产生block内的寄存器定义;
union ${block_name}_${reg_name}_tu{  //1.1 block内每个寄存器的union定义;
   struct {  //SW_access=??,  reg_type=xx;   #只产生reg_type=cfg/status/toggle/irq类型的寄存器,  不产生slave/mem类型;
      u32 a        : 8;  //default = ??;
      u32 rsv15_8  : 8;
      u32 b        : 4;  //default = ??;
      u32 rsv31_20 : 12;
   }bits;
   u32 word;
};
... //把每个reg_name的寄存器联合体都声明;

struct ${block_name}_reg_ts{   //1.2 block的所有寄存器声明汇总;
   union ${block_name}_${reg_name1}_tu ${reg_name1};
   union ${block_name}_${reg_name2}_tu ${reg_name2};
};

//2. 按照address_map, 产生"树形图"所有block的 reg_addr->reg_default_value的映射关系;
```

4. 在out/firmware/目录下, 产生"out/firmware/xxx_all_reg_addr.h + out/firmware/xxx_all_reg_type.h"这两个文件;

# 寄存器工具配套环境

1. 产生amba和csr_bus协议互转的模块
   - 在auxi/common_ip/目录下, 所有模块前缀是COM_CSR_CVT_*
   - apb2csr=COM_CSR_CVT_APB2CSR, axil2csr=COM_CSR_CVT_AXIL2CSR, ahb2csr=COM_CSR_CVT_APB2CSR,  csr2apb=COM_CSR_CVT_CSR2APB,  csr2axil=COM_CSR_CVT_CSR2AXIL, y
2. 产生csr_bus访问sram接口的模块,
   - 在auxi/common_ip/目录下, 模块名是 COM_CSR2RAM;
   - csr和ram的数据位宽相同;
   - ram接口信号
```verilog
output wire [RAM_AW-1:0]        o_tx_ram_wr_addr         ,
output wire [RAM_DW-1:0]        o_tx_ram_wr_data         ,
output wire [RAM_STRB-1:0]      o_tx_ram_wr_vld          ,
input  wire                     i_tx_ram_wr_rdy          ,
output wire [RAM_AW-1:0]        o_tx_ram_rd_addr         ,
output wire                     o_tx_ram_rd_vld          ,
input  wire                     i_tx_ram_rd_rdy          ,
input  wire [RAM_DW-1:0]        i_tx_ram_rd_data         ,
input  wire                     i_tx_ram_rd_ack          ,
```
3. 产生csr_bus的regslice模块
   - 在auxi/common_ip/目录下, 模块名是 COM_CSR_REGSLICE;
   - 输入输出都是csr_bus,  vld/rdy双向隔离
4. 产生gen_tb脚本,
5. 产生testbench;

# 问题记录

1. 以top_reg.md, 跑单模块模式;  反复查看输出内容, 对齐输出格式;     //另外, 单模块/嵌套这两种模式, 比较拗口, 请gemini想几个模式名称候选;
2. 现在问题是, 跑的嵌套模式,  我们先只输出.md格式, 请把.md格式打印出来, 先在网页上看到输出格式, 麻烦一点的我下载到本地运行, 减少下载到本地的次数;
3. offset自动补全做的很好， 我现在把reg_name写了几个相同的； 请你再处理下， 观察去重内容；
4. 在nested模式下, 对应rule8 + special.3 reg_type=slave;  如果填了bytesize, 检查是否超过可用地址空间; 如果没填bytesize, 从当前reg_name+下一行reg_name, 可推导bytesize可用大小;
5. 打印出错信息时, 把当前位置+前一个位置的寄存器所有填写内容都打印出来;
6. 打印出错信息时, 不用带着rule8等内容， 只带着用户填写的寄存器表格可见的内容;   rule1~rule8等仅仅是开发对齐需要, 不暴露给用户;
7. 在nested模式下, 丰富输出内容格式, 我想增加html作为输出格式:
   - 用flash或django等框架, 产生离线html文件格式, 可以.html通过浏览器看到更好的格式呈现。
   - 最好是公司内网能获取的第三方包, 可能是flash?  请gemini推荐一个;  公司内网一般是linux操作系统，不能连接外网, 要通过离线包安装第三方包;
   - csr_tool增加包检测功能, (1)最基础用markdown格式, 在win/mac/linux任意环境都能跑, 几乎不依赖第三方包;  (2)增加输出内容为html格式, 检查第三方包是否存在, 若不存在, 只用基础markdown也能工作;
   - 在html格式中, 也类似markdown格式, 有address_map+每个module节点的寄存器定义; (1)在address_map中增加超链接, 点击跳转到对应的寄存器定义; (2) 每个module的标题, 可以折叠/展开, 查看子模块的寄存器定义;
8. 刷新README.md内容, 以前内容都不要, 按当前内容刷新;
   - 最开始简介工具功能(50字左右), 然后面向使用者, 说明如何运行;
   - 面向rtl单个module用户, 说明填表方式, 规则, 输出内容;
   - 面向rtl集成者/top验证/固件开发者, 简介嵌套模式输出内容;
   - 面向共同的该工具开发者, 说明中间变量数据结构, 如何按tree结构遍历;  方便以后生成rtl/tb/firmware;
9. 增加输入输出文件格式excel格式,  (1) 调用openpyxl第三方包;  (2) 如果该包不存在， 和jinji2类似提示包不存在, 但markdown基础格式仍可运行;   (3) tree结构的excel输出, 第一个sheet输出address_map, 后面每个sheet输出一个module节点; (4) 好像excel有sheet导航栏, 类似网页标题目录形式, 点击可以跳转到对应sheet;  如果openpyxl能生成该导航栏就生成, 生成不了就忽略导航栏功能。
10. 近期规划: (1) 中间json格式内容对齐, (2) 生成好readme.md,  (3) firmware.h内容对齐, (4) src/目录下, python源代码组织，可以多一些文件, 单个文件不超过500~1000行, 公用函数可以提取xx_common.py;
11. 中级规划: 开始rtl生成, (1) reg_bus定义, 高性能; (2) reg_bus到rtl实现, shadow N/repeat N的检查 (3) 输出接口封装为struct/package形式; (4) 开发配套功能, a. amba2reg_bus协议转换, axi/axi_lite/apb/ahb与reg_bus的互转, b. reg_bus.regslice功能, 远距离打拍, c. reg_bus.demux功能, 适配reg_type=slave/mem;  d. reg_bus to sram_access功能;
12. 当reg_type=slave的时候,  如果没有slv_filename, 或filename对应的文件不存在， 要报错退出;
13. xxx_all_reg_type.h中, 只产生reg_type=cfg/status/toggle/irq类型的寄存器,  不产生slave/mem类型;
14. static npu_top_init_ts npu_top_init = {}; 这个会产生程序存储空间, 希望xxx_all_reg_type.h中, 全部是类型声明。  这里考虑改成一个init_func()函数声明？
15. 注释都用英文注释， 只使用//行注释, 不使用/**/块注释;
16. ${block_name}_reg_ts改成${block_name}_block_reg_ts, 强调是1个block内所有寄存器的集合。
17. 本次问题:
   - 在xx_all_reg_type.h中, 不用`typedef uint32_t u32;`, 把后面所有的u32, 全部换成uint32_t;
   - 在xx_all_reg_type.h的addr/default_val部分, 只有struct/function的声明和定义, 没有实例化，不占用程序空间。对于`typedef const struct {}xx_init_ts`, 可以在struct里面带一个addr/default映射关系的函数声明, 在struct外面定义这个函数。
18. 当前gen_rtl基本已对齐,  剩余的内容:
   - special填写 shadow和shadow N;  y
   - 产生tb, 测试CSR读写行为;
   - 产生apb2csr, axi_lite2csr, ahb2csr协议转换模块;  产生csr2apb, csr2axi_lite协议转换模块；  y
19. 开始tb组件生成， 支持UVM_REG, 支持BLOCK嵌套集成。
20. readme说明， gen rtl/tb/fw的位置
21. sv/vhdl/c保留关键字检查