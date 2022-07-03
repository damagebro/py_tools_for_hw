/******************************************************************************
*
*  Authors:   dmg
*    Email:   dmg@sensetime.com
*     Date:   2019/11/06-09:56:24
*
*  Description:
*  -
*
*  Modify:
*  -2020/09/21, modify by ty:
*   when rd_empty, rd_data=0; to prevent x_state propagate
*
******************************************************************************/

`ifndef com_sync_fifo_reg_v
`define com_sync_fifo_reg_v
module com_sync_fifo_reg #( parameter
    DW      = 8,
    DEPTH   = 4,
    AW      = $clog2(DEPTH+1)
)
(
input  wire                     clk                 ,
input  wire                     rst_n               ,
input  wire                     clear               ,

input  wire                     wr_en               ,
input  wire [DW-1:0]            wr_data             ,
output wire                     wr_full             ,
input  wire                     rd_en               ,
output wire [DW-1:0]            rd_data             ,
output wire                     rd_empty            ,
output wire [AW-1:0]            water_level         //,
);
//localparam-----------------------------------------------------------------
// localparam AW = $clog2(DEPTH+1);
//reg  declare---------------------------------------------------------------
reg  [DEPTH-1:0][DW-1:0] arc_mem;
//wire declare---------------------------------------------------------------
wire full;
wire empty;
//statement------------------------------------------------------------------

wire [AW-1:0] wr_addr;
wire [AW-1:0] rd_addr;
com_sync_fifo_ctrl #(
    .DEPTH      ( DEPTH      )  //4
)u_com_sync_fifo_ctrl
(
    .clk                  ( clk                  ), //i
    .rst_n                ( rst_n                ), //i
    .clear                ( clear                ), //i

    .wr_en                ( wr_en                ), //i
    .wr_addr              ( wr_addr              ), //o
    .wr_full              ( wr_full              ), //o
    .rd_en                ( rd_en                ), //i
    .rd_addr              ( rd_addr              ), //o
    .rd_empty             ( rd_empty             ), //o
    .water_level          ( water_level          )  //o
);

//mem
always @(posedge clk)
begin
    if( wr_en && !wr_full ) begin
        arc_mem[ wr_addr ] <= wr_data;  //spyglass disable ResetFlop-ML
    end
end
// assign rd_data = rd_empty ? DW'(0) : arc_mem[ rd_addr ];
assign rd_data = arc_mem[ rd_addr ];

endmodule //end of com_sync_fifo_reg
`endif //end of com_sync_fifo_reg_v
