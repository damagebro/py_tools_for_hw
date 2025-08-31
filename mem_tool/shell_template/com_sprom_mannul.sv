/******************************************************************************
*
*  Authors:   moc,dmg
*    Email:   dmg@sensetime.com
*     Date:   2025/07/07-20:01:49
*
*  Description:
*   if use rom_shell, rom_shell must intergrated by this rom_mannul module;
*   the rom_mannul goal: when sim/emu/fpga verify flow, rom_code use "tie value" rather than initial from file, only synthesis_flow rom_lib initial from file;
*   the designer responsibility: (1)tie rom_value in this module, (2)each rom_module, copy this file and change file_name+module_name; (3)move each rom_module to project_path;
*
*  Modify:
*  -
*
******************************************************************************/

module com_sprom_mannul#(
parameter  DATA_W   = 32           , //range=[1:], Data width of memory.
parameter  DEPTH    = 64           , //range=[1:], Depth of memory.
parameter  MEM_USER = 0            , //range=[0:], Memory user diy
localparam ADDR_W   = $clog2(DEPTH)  // Address width,
)(
input  wire                   clk    ,
input  wire [`COM_SYS_W-1:0]  sys_cfg,

input  wire                   rd_en   ,
input  wire [ADDR_W-1:0]      rd_addr ,
output wire [DATA_W-1:0]      rd_data//,
);

`ifdef COM_RAM_AS_REG
    reg  [DATA_W-1:0] w_tie_romfile[0:DEPTH];
    reg  [DATA_W-1:0] r_rd_data;
    always @( posedge clk )begin
        if( rd_en )
            r_rd_data <= w_tie_romfile[rd_addr];
    end
    always@* begin   //##############################tie here####################################
        w_tie_romfile[0] = '0;
        w_tie_romfile[1] = '1;
        // ...
    end

    com_sprom_shell #(  //only for rom_shape print to rom_lst;
        .DATA_W               ( DATA_W              ), //32
        .DEPTH                ( DEPTH               ), //64
        .MEM_USER             ( MEM_USER            )  //0
    )u_com_sprom_shell_for_rpt
    (
        .clk                 ( '0             ), //i
        .sys_cfg             ( '0             ), //i
        .rd_en               ( '0             ), //i
        .rd_addr             ( '0             ), //i
        .rd_data             (                )  //o
    );
`else
    com_sprom_shell #(
        .DATA_W               ( DATA_W              ), //32
        .DEPTH                ( DEPTH               ), //64
        .MEM_USER             ( MEM_USER            )  //0
    )u_com_sprom_shell(
        .clk                 ( clk                  ), //i
        .sys_cfg             ( sys_cfg              ), //i
        .rd_en               ( rd_en                ), //i
        .rd_addr             ( rd_addr              ), //i
        .rd_data             ( rd_data              )  //o
    );
`endif

endmodule
