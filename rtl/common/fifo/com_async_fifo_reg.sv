/******************************************************************************
*
*  Authors:   dmg
*    Email:   dmg@sensetime.com
*     Date:   2019/11/15-09:20:22
*
*  Description:
*  -water_level means (async_fifo_depth, only in src_clk domain)
*  -when wr_full, the storeged data tol_num=(DEPTH+1);
*
*  Modify:
*  -2020/09/16, modify by dmg:
*   data register out, to isolated datapath in dst_clk domain, from afifo.arc_mem to rc_out_data;
*
******************************************************************************/

//`include "com_cdc_hs.v"
//`include "com_cdc_rstn.v"
//`include "com_cdc_sig.v"

`ifndef com_async_fifo_reg_v
`define com_async_fifo_reg_v
module com_async_fifo_reg #( parameter
    DW    = 8,
    DEPTH = 4,
    AW    = $clog2(DEPTH+1)
)
(
input  wire                     wr_clk              ,
input  wire                     wr_rst_n            ,
input  wire                     wr_clear            ,
input  wire                     rd_clk              ,
input  wire                     rd_rst_n            ,
input  wire                     rd_clear            ,

input  wire                     wr_en               ,
input  wire [DW-1:0]            wr_data             ,
output wire                     wr_full             ,
input  wire                     rd_en               ,
output wire [DW-1:0]            rd_data             ,
output wire                     rd_empty            ,
output wire [AW-1:0]            water_level         //,
);
//localparam-----------------------------------------------------------------
//reg  declare---------------------------------------------------------------
reg  [DEPTH-1:0][DW-1:0] arc_mem;
//wire declare---------------------------------------------------------------
wire [1:0] afifo_wr_reset_signals; //0:sync_wr_rst_n, 1:sync_wr_clear;
wire [1:0] afifo_rd_reset_signals; //0:sync_rd_rst_n, 1:sync_rd_clear;
wire sync_wr_rst_n = afifo_wr_reset_signals[0]; //wr clk domain
wire sync_wr_clear = afifo_wr_reset_signals[1]; //wr clk domain
wire sync_rd_rst_n = afifo_rd_reset_signals[0]; //rd clk domain
wire sync_rd_clear = afifo_rd_reset_signals[1]; //rd clk domain
//statement------------------------------------------------------------------

wire          afifo_wr_en   = wr_en;
wire          afifo_wr_full ;
wire [AW-1:0] afifo_wr_addr ;
wire          afifo_rd_en   ;
wire          afifo_rd_empty;
wire [AW-1:0] afifo_rd_addr ;
com_async_fifo_ctrl #(
    .DEPTH      ( DEPTH      )  //4
)u_com_async_fifo_ctrl
(
    .wr_clk               ( wr_clk               ), //i
    .wr_rst_n             ( wr_rst_n             ), //i
    .wr_clear             ( wr_clear             ), //i
    .rd_clk               ( rd_clk               ), //i
    .rd_rst_n             ( rd_rst_n             ), //i
    .rd_clear             ( rd_clear             ), //i
    .wr_reset_signals     ( afifo_wr_reset_signals ), //o
    .rd_reset_signals     ( afifo_rd_reset_signals ), //o

    .wr_en                ( afifo_wr_en          ), //i
    .wr_addr              ( afifo_wr_addr        ), //o
    .wr_full              ( afifo_wr_full        ), //o
    .rd_en                ( afifo_rd_en          ), //i
    .rd_addr              ( afifo_rd_addr        ), //o
    .rd_empty             ( afifo_rd_empty       ), //o
    .water_level          ( water_level          )  //o
);

//mem
always @(posedge wr_clk or negedge sync_wr_rst_n)
begin
    if( !sync_wr_rst_n ) begin
        arc_mem <= 'b0;
    end
    else if( afifo_wr_en && !afifo_wr_full ) begin
        arc_mem[ afifo_wr_addr ] <= wr_data;
    end
end
wire [DW-1:0] afifo_rd_data = arc_mem[ afifo_rd_addr ];

//sync data to dst_clk domain, register out---
reg  rc_out_flag;
reg  [DW-1:0] rc_out_data;
wire out_wr_en = afifo_rd_en;
wire out_rd_en = rd_en;
always @(posedge rd_clk or negedge sync_rd_rst_n)
begin
    if( !sync_rd_rst_n )
        rc_out_flag <= 1'b0;
    else if( sync_rd_clear )
        rc_out_flag <= 1'b0;
    else if( afifo_rd_en )
        rc_out_flag <= 1'b1;
    else if( rd_en )
        rc_out_flag <= 1'b0;
end
always @(posedge rd_clk or negedge sync_rd_rst_n)
begin
    if( !sync_rd_rst_n )
        rc_out_data <= 'b0;
    else if( out_wr_en )
        rc_out_data <= afifo_rd_data;
end
assign afifo_rd_en = !afifo_rd_empty && (!rc_out_flag || rd_en);


//out---
//src_clk domain---
assign wr_full     = afifo_wr_full;
//dst_clk domain---
assign rd_data =  rc_out_data;
assign rd_empty= !rc_out_flag;

endmodule //end of com_async_fifo_reg
`endif //end of com_async_fifo_reg_v

