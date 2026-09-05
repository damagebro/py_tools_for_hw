/******************************************************************************
*
*  Authors:   moc,dmg
*    Email:   dmg@sensetime.com
*     Date:   2025/07/07-20:01:49
*
*  Description:
*  - USER_EDIT_REQUIRED: copy this template for each ROM and manually tie all
*    ROM values below. The memory tool never overwrites an existing file.
*  - Simulation, emulation and FPGA use tied values; synthesis uses ROM cells.
*
******************************************************************************/

module com_sprom_manual #( parameter
    DATA_W   = 32, //range=[1::]
    DEPTH    = 64, //range=[1::]
    MEM_USER = 0,
    localparam ADDR_W = $clog2(DEPTH)
)
(
input  wire                         clk                 ,
input  wire [`COM_MEM_CTRL_W-1:0]   i_cfg_mem_ctrl      ,

input  wire                         i_rd_en             ,
input  wire [ADDR_W-1:0]            i_rd_addr           ,
output wire [DATA_W-1:0]            o_rd_data           //,
);
`ifdef COM_RAM_AS_REG
//signal declare-------------------------------------------------------------
reg [DATA_W-1:0] w_tie_romfile[0:DEPTH-1];
reg [DATA_W-1:0] r_rd_data;

//statement------------------------------------------------------------------
//output assign---
assign o_rd_data = r_rd_data;

//body---
always @(posedge clk) begin
    if( i_rd_en )
        r_rd_data <= w_tie_romfile[i_rd_addr];
end

always @* begin
    for( int i=0; i<DEPTH; i++ )
        w_tie_romfile[i] = '0;
    // USER_EDIT_REQUIRED: tie ROM entries here.
end

//instance----
com_sprom_shell #(
    .DATA_W              ( DATA_W             ),
    .DEPTH               ( DEPTH              ),
    .MEM_USER            ( MEM_USER           )
)u_com_sprom_shell_rpt
(
    .clk                 ( '0                 ), //i
    .i_cfg_mem_ctrl      ( '0                 ), //i
    .i_rd_en             ( '0                 ), //i
    .i_rd_addr           ( '0                 ), //i
    .o_rd_data           (                    )  //o
);
`else
//instance----
com_sprom_shell #(
    .DATA_W              ( DATA_W             ),
    .DEPTH               ( DEPTH              ),
    .MEM_USER            ( MEM_USER           )
)u_com_sprom_shell
(
    .clk                 ( clk                ), //i
    .i_cfg_mem_ctrl      ( i_cfg_mem_ctrl     ), //i
    .i_rd_en             ( i_rd_en            ), //i
    .i_rd_addr           ( i_rd_addr          ), //i
    .o_rd_data           ( o_rd_data          )  //o
);
`endif

endmodule //end of com_sprom_manual
