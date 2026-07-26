# 计划

1. 完全重写gen_rtl_inst, 自动实例化rtl代码;
2. 重写csr_tool, autogen_reg是以前的寄存器工具， 新建一个csr_tool目录，完全重写
3. mem_tool是前端sram相关工具， 读了代码写一些readme；
4. 所有工具考虑如何发布, vscode插件一种方式,  linux环境module load也要做
5. 逐渐增加其他rtl工具


# gen_tb_env

做一个生成tb环境框架的python脚本,  基于该tb_demo, 再生成`axi_vip/apb_vip/ahb_vip`等常用tb环境;

## 生成 tb_demo

1. 基于`C:\personal\proj\ai_proj\dmg\com\impl_template\memory\mem_tool\templates\py_sim`,  在`xx/ai_proj\dmg\py_tools_for_hw`目录下, 新建`py_rtl_sim`目录, 在新建`py_rtl_sim/gen_tb_demo/`目录，放py_sim的内容;
2. 到此暂停，人工检查`gen_tb_demo`

## axi_vip

1. 基于`gen_tb_demo`, 产生`sim_axi_vip`目录, 里面放axi_interface, axi_master, axi_slave的tb环境;
2. axi_master要求: (1)通过配置文件指定axi_master行为, (2) 可配置axi的基地址, 数据量大小, 和数据内容;  (3) 可配置数据内容, 可以是`data=addr`形式, 方便debug; 也可以是`file.bin`二进制文件指定; (4) 可配置axi_awvalid激励的行为, 可以连续产生，也可以随机间断。
3. axi_slave要求: (1)通过同一个配置文件指定axi_slave行为, (2) 可配置axi_slave_mem的容量大小, 数据内容可以是`data=addr`, 也可以通过`file.bin`初始化mem数值; (3) 可配置axi_reoder_depth, =0不乱序, =16只在近16个id中乱序; (4) 可配置axi_awready相应行为, 可以连续产生，也可以随机间断。
4. axi_vip, 支持N个axi_master, 访问同一个axi_slave;  不再支持N个axi_master/slave成对，每个1to1访问;

## apb_vip

1. 基于`gen_tb_demo`, 产生`sim_apb_vip`目录, 里面放`apb_interface, apb_master`的tb环境;
2. 发起apb_master激励
3. apb_vip, 支持`txt`的apb_master数据内容文件，内容形式:
```
0x00001000 0x12345678   #addr data  #comment, #后面是可选的comment注释
0x00001004 0x1
0x00001008    0x2
0x00001020    0x6

0x00002020    0xdeadbeef
#空格, 换行都可忽略， 只解析`addr data`, 然后逐个发激励
```

## ahb_vip

1. 基于`gen_tb_demo`, 产生`sim_ahb_vip`目录, 里面放`ahb_interface, ahb_master`的tb环境;
2. 发起ahb_master激励


# gen_rtl_dummy

在`xx/ai_proj\dmg\py_tools_for_hw`目录下, 新建`gen_rtl_dummy`目录， 生成后面功能的脚本

输入rtl绝对路径的文件，输出rtl挖空后的module, 有3种挖空模式:
- bbox, 挖空后，所有output tie0;
- stub, 纯粹挖空, input/output都悬空;
- port_direction_invert,  挖空后，所有input端口换成output,  所有output换成input;  如果信号名是[i_|o_]风格， 把i_->o_, o_->i_;
