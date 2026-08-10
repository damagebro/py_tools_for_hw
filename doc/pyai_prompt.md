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

# 考虑如何发布

以下问题都先逐一回答, 暂时不生成

- gen_rtl_inst, 如何在rtl代码编辑的现场，调用并例化其他module;
- 做成vscode plugin的方法, 演示如何使用;
- 做成linux下面， module load的方法;
- 做一个py_tool搜集器, 其他工具都通过py_tool调用;

目前`py_tools_for_hw\hw_tool\bin\hw_tool.cmd`, 已可以汇总所有工具；通过linux module load发布应该会比较简洁, 但发布vscode 插件似乎会有不同，讨论vscode插件发布:
- csr_tool, 如何在vscode界面和用户交互？ 可能不是刚需, 因为module load能调出命令也可。
- gen_rtl_inst, 强烈需要在vscode编辑过程中, 和用户交互
  - (1) 调用`dmg\com\common\fifo\com_sync_fifo_reg.sv`, 能比较方便生成他们的instance例化代码片段;
  - (2) 调用任意abs_path/module_file, 可以在当前编辑文件产生例化代码片段；
以上这些如何实现



# 新增工具

## 多git仓库代码管理

背景: 对项目多个git仓库, 统一pull, 锁定main分支, 打tag， 解除main分支锁定。  google的`repo`工具很合适, 把git仓库按flat扁平化统一维护, `fusesoc`也有按tree结构维护所有git仓库。  flat/tree结构各有优劣, flat可以全公司统一打平, 但权限要全开放; tree可以只看到自己那部分权限, 但项目交付期间，top要拉齐版本， tree跨node版本统一比较繁琐。
目标: 结合`repo` + `fusesoc`工具优劣, 规划一个"多仓库代码管理工具", 规划结果写到`C:\personal\proj\ai_proj\dmg\py_tools_for_hw\doc\plan_git_repo.md`;

调整`git_repo_mgr/README`章节顺序,
- 简介
- 对比`repo/fusesoc`工具的优劣,  说明新开发git_repo工具的初衷
  - `repo`是flat结构, 批量拉取仓库/切分支/打tag方便，但权限管理/写好manifest比较繁琐;
  - `fusesoc`的tree结构, 只依赖相邻node获取仓库比较方便, 但修改跨node版本/跨node版本冲突/批量切分支/打tag/发版锁定版本很繁琐。
- 精简命令说明, 侧重熟练者查询命令和使用;
- 其他必要章节


## rtl filelist维护

背景: 传统filelist通过`RTL_PATH`等变量, 锁定项目根目录之后, 所有项目的子目录都要固定目录层级, 然后才能把filelist写完整。 `fusesoc`推出了`corefile`, 让每个子目录分布式自己管理, 当顶层要集成多个`corefile`的时候, 通过`corefile`唯一化标识的`core_id`可先定位到每个子目录, 然后根据子目录的`corefile`相对路径，可整理出完整的top_filelist;
目标: 结合`fusesoc`的优势, 给出一个rtl_filelist维护方式, 并考虑: (1) 有的后端文件需要绝对路径, (2) emu/fpga的flist会删除一些文件; (3) 后端分harden综合, 每个harden会去掉不可综合的仿真模型,  上传harden只需要子harden的空壳文件(stub), 不需要子harden内部其他模块的文件。
规划结果写到`C:\personal\proj\ai_proj\dmg\py_tools_for_hw\doc\plan_rtl_filelist.md`;


### 讨论corefile格式

1. flag
flist常见，  sim/synth/lint,  后面兼容emu/fpga再说，
- sim: 默认模式，所有文件都解析，可不需要flag；
- synth = is_synth,  综合harden标记,
  - harden_top保留stub(需要指定top_module_name),  harden内部文件都挖空。
  - dw/sram_sim_model等不可综合文件都去除
- lint = is_lint,
  - harden内部文件都保留
  - dw/sram_sim_model等不可综合文件都去除

另外考虑的功能:
- syn -> synth;
- 讨论是否harden的时候一定要指定top_module?  no
- flist去重

###  调整`rtl_flist_mgr/README`章节顺序,

- 简介
- 设计初衷, 充分借鉴fusesoc的corefile + core_id, 让filelist去中心化;  但找回一些对`legacy.f`的维护, 让`sram_sim_model`等不好做成corefile的, 也可以按原始`rtl_filelist.f`进行编写;
- 精简命令说明, 侧重熟练者查询命令和使用;
- 其他必要章节


###  其他

1. 用.rtl_flist/xx, 扫描一次corefile list之后，可以缓存起来加速(不再扫描root_dir/import/)， 强制rescan才重新扫描;   y
2. 现在示例有.rtl_flist吗;  y
3. 有一个标记， 让对应的file/fileset, 丢到flist最开头;
4. 如果以后有新的flag, is_emu/is_fpga等, 如何扩展？  但推荐flag收敛;  y
5. 如果root_dir下面, 既有core.toml, 也有normal.toml, 如何区分;  //y, 文件开头的[core]可区分
6. flist去重

| root_dir/
|---|import/
|---|---|cpu/
|---|---|---|spram100x10.sv
|---|---|npu/
|---|---|---|spram100x10.sv   //不去重

| root_dir/
|---|import/
|---|---|com/
|---|---|---|spram100x10.sv
|---|---|cpu/  #depend com
|---|---|npu/  #depend com


