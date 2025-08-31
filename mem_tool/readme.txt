# 使用说明
python ./src/gen_sram_excel.py -p cpu

(1)只生成sram_shell: python ./src/gen_sram_excel.py -p cpu [-w ./out/];   #shell输出路径是: ./out/
(2)跑仿真得到sram_rpt: TBD;
(3)生成sram_excel: python ./src/gen_sram_excel.py -p cpu -m excel -w ./bin/ -x cpu_20250730_memory_require.xlsx -xcka 1500 [-xckb 1000]
    #rpt输入路径是: ./bin/spram.lst,./bin/tpram1ck.lst...;
    #excel输出路径是: ./bin/cpu_20250730_memory_require.xlsx;
(4)例化instance: python ./src/gen_sram_excel.py -p cpu -m inst -w ./bin/ {-x cpu_20250730_memory_require.xlsx|}
    #shell输出路径是: ./bin/;
    #如果有-x,则从excel中得到所有sram_list然后instance;
    #如果没有-x, 则./bin/spram.lst,./bin/tpram1ck.lst... 得到所有sram_list然后instance;

# 目录结构
|sram_cfg.json   #脚本配置文件
|run.sh          #可以直接 ./run.sh; 文件内容是` python3 ./src/gen_sram_excel.py [sram_cfg.json] `
|src/            #python脚本源代码
|---|gen_sram_excel.py
|shell_template/ #rtl模板文件, sram_shell.sv + ecc_sram_shell.sv;
|sim_template/   #运行vcs仿真的简易testbench环境;


# 实现方式
(1) gen_sram_shell 模式
假设sram_cfg.json中的 subsys_prefix="cpu";
拷贝'./shell_template/'目录下， 把rtl模板文件带上sram_cfg.json中指定的前缀， spram_shell.sv+tpram1ck_shell.sv+tpram2ck_shell.sv+sprom_shell.sv, ecc_spram_shell.sv+ecc_tpram1ck_shell.sv+ecc_tpram2ck_shell.sv, sprom_manual.sv;
输出到./bin/目录下， cpu_spram_shell.sv, cpu_ecc_spram_shell.sv, cpu_sprom_manual.sv ...;

(2) gen_sram_list 模式
运行vcs仿真，打印所有sram形状对应的parameter， 输出到./bin/xxram.lst;
依赖sram_cfg.json指定的'rtl_filelist'和'top_module_name',
a. 拷贝'./sim_template/'目录下的仿真环境，拷贝到'./tmp/'目录;
b. 修改仿真环境中的filelist, 修改仿真环境中的top.sv集成'top_module_name';
c. 启动仿真，打印结果在./tmp/bin/xxram.lst文件中, 把该文件拷贝到./bin/xxram.lst;

(3) gen_sram_excel模式
输入./bin/xxram.lst, 输出./bin/{excel_filename}; excel格式方便前后端交互。
excel中有指定memory_compiler的ppa策略, 有sram时钟频率等, 有些需要再'手动检查'一遍。
对于时钟频率, 默认用本json文件指定的频率, 若读写时钟频率相同,则只使用'default_ram_wr_clk';
另外, 若sram_shell的MEM_USER参数非0, 优先用MEM_USER指定的频率, MEM_USER指定时钟频率的方式每个项目统一约定, 且需修改python脚本。

(4) gen_sram_instance模式
输入./bin/{excel_filename}, 输出./bin/<subsys_prefix>_sram_shell.sv;
在所有'<subsys_prefix>_sram_shell.sv'文件中，集成sram_excel中所有ram尺寸对应的sram_wrapper， 把后端memory_compiler生成的真实sram，并封装为sram_wrapper之后，集成到sram_shell中。 让前端例化的sram_shell和真实sram关联起来。


# sram_wrapper命名规则
{subsys_prefix}_{sram_type}_{depth}X{width}[X{strobe_w}][_{suffix}]
subsys_prefix: subsys前缀, cpu/npu/pcie等;


# sram_shell选各种形状sram_wrapper的rtl代码片段；
module sram_shell #(
    parameter WID_DAT  = 32,
    parameter VOL_DAT  = 64,
    parameter WID_STB  = 1 ,
    parameter MEM_USER = 0
    ...
)
generate  //通过generate_if，根据不同的参数例化不同尺寸的sram_wrapper
    if( WID_DAT==32 && VOL_DAT==64 && WID_STB==1 && MEM_USER==0 ) begin:gen_sram_phy
        cpu_sram_64x32_wrapper u_cpu_sram64x32_wrapper(...);
    end:gen_sram_phy
    else if( WID_DAT==100 && VOL_DAT==64 && WID_STB==2 && MEM_USER==0 ) begin:gen_sram_phy
        cpu_sram_64x100x2_wrapper u_cpu_sram64x32_wrapper(...);
    end:gen_sram_phy
    else if( WID_DAT==100 && VOL_DAT==64 && WID_STB==1 && MEM_USER==1500 ) begin:gen_sram_phy
        cpu_sram_64x100_usr1500_wrapper u_cpu_sram64x32_wrapper(...);
    end:gen_sram_phy
    ...
endgenerate
endmodule
