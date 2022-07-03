/******************************************************************************
*
*  Authors:   dmg
*    Email:   dmg@sensetime.com
*     Date:   2019/11/15-09:20:22
*
*  Description:
*  -water_level means (async_fifo_depth, only in src_clk domain)
*
*  Modify:
*  -2022/3/22, support DEPTH=2*n;
*
******************************************************************************/

//`include "com_cdc_hs.v"
//`include "com_cdc_rstn.v"
//`include "com_cdc_sig.v"

`ifndef com_async_fifo_ctrl_v
`define com_async_fifo_ctrl_v
module com_async_fifo_ctrl #( parameter
    DEPTH = 4,
    AW    = $clog2((DEPTH>2?DEPTH:2)+1)
)
(
input  wire                     wr_clk              ,
input  wire                     wr_rst_n            ,
input  wire                     wr_clear            ,
input  wire                     rd_clk              ,
input  wire                     rd_rst_n            ,
input  wire                     rd_clear            ,
output wire [1:0]               wr_reset_signals    , //0:sync_wr_rst_n, 1:sync_wr_clear;
output wire [1:0]               rd_reset_signals    , //0:sync_rd_rst_n, 1:sync_rd_clear;

input  wire                     wr_en               ,
output wire [AW-1:0]            wr_addr             ,
output wire                     wr_full             ,
input  wire                     rd_en               ,
output wire [AW-1:0]            rd_addr             ,
output wire                     rd_empty            ,
output wire [AW-1:0]            water_level         //,
);
//localparam-----------------------------------------------------------------
`COM_PARAM_ASSERT( DEPTH>=2, "fifo depth must larger than 0" );
`COM_PARAM_ASSERT( DEPTH%2==0, "fifo depth must be 2*n" );

localparam DEPTH_L2 = $clog2(DEPTH);
localparam DEPTH_P2 = 1<<DEPTH_L2;
//reg  declare---------------------------------------------------------------
reg  [AW-0:0] rc_wrcnt;
reg  [AW-0:0] rc_wrcnt_gray;
reg  [AW-0:0] rc_rdcnt;
reg  [AW-0:0] rc_rdcnt_gray;
//wire declare---------------------------------------------------------------
wire [AW-1:0] depth_half = DEPTH_P2>>1;
wire [AW-1:0] depth_comp = DEPTH_P2-DEPTH;
wire [AW-1:0] depth_comp_half = depth_comp>>1;
wire [AW-1:0] depth_jump = depth_half - depth_comp_half;

wire clk_s   = wr_clk   ;
wire rst_n_s = wr_rst_n ;
wire clear_s = wr_clear ;
wire clk_d   = rd_clk   ;
wire rst_n_d = rd_rst_n ;
wire clear_d = rd_clear ;

//src_clk domain---
wire           afifo_wr_en   = wr_en;
wire           afifo_wr_full ;
//dst_clk domain---
wire           afifo_rd_en   = rd_en;
wire           afifo_rd_empty;
//statement------------------------------------------------------------------
//rst & clear
wire rst = rst_n_s && rst_n_d;
wire rst_src_sync;
wire rst_dst_sync;
com_cdc_rstn r_com_cdc_rstn_src ( .sclk(clk_s), .irst_n(rst), .srst_n(rst_src_sync) );
com_cdc_rstn r_com_cdc_rstn_dst ( .sclk(clk_d), .irst_n(rst), .srst_n(rst_dst_sync) );

wire ps_clear_s;
wire ps_clear_d;
com_edge_detect #( .MODE("posedge") ) zr_com_edge_detect_clrs( .clk(clk_s), .rst_n(rst_src_sync), .level_in(clear_s), .pulse_out(ps_clear_s) );
com_edge_detect #( .MODE("posedge") ) zr_com_edge_detect_clrd( .clk(clk_d), .rst_n(rst_dst_sync), .level_in(clear_d), .pulse_out(ps_clear_d) );

wire clear_req_s2d;
wire clear_ack_d2s;
reg  rc_src_clr_ongoing;
always @(posedge clk_s or negedge rst_src_sync)
begin
    if( !rst_src_sync )
        rc_src_clr_ongoing <= 1'b0;
    else if( ps_clear_s )
        rc_src_clr_ongoing <= 1'b1;
    else if( clear_ack_d2s )
        rc_src_clr_ongoing <= 1'b0;
end
com_cdc_pulse zr_com_cdc_pulse_clr_req_s2d(
    .iclk      ( clk_s        ),  //i
    .irst_n    ( rst_src_sync ),  //i
    .ipulse    ( ps_clear_s   ),  //i
    .oclk      ( clk_d        ),  //i
    .orst_n    ( rst_dst_sync ),  //i
    .opulse    ( clear_req_s2d)//,//o
);
com_cdc_pulse zr_com_cdc_pulse_clr_ack_d2s(
    .iclk      ( clk_d        ),  //i
    .irst_n    ( rst_dst_sync ),  //i
    .ipulse    ( clear_req_s2d),  //i
    .oclk      ( clk_s        ),  //i
    .orst_n    ( rst_src_sync ),  //i
    .opulse    ( clear_ack_d2s)//,//o
);

wire clear_req_d2s;
wire clear_ack_s2d;
reg  rc_dst_clr_ongoing;
always @(posedge clk_d or negedge rst_dst_sync)
begin
    if( !rst_dst_sync )
        rc_dst_clr_ongoing <= 1'b0;
    else if( ps_clear_d )
        rc_dst_clr_ongoing <= 1'b1;
    else if( clear_ack_s2d )
        rc_dst_clr_ongoing <= 1'b0;
end
com_cdc_pulse zr_com_cdc_pulse_clr_req_d2s(
    .iclk      ( clk_d        ),  //i
    .irst_n    ( rst_dst_sync ),  //i
    .ipulse    ( ps_clear_d   ),  //i
    .oclk      ( clk_s        ),  //i
    .orst_n    ( rst_src_sync ),  //i
    .opulse    ( clear_req_d2s)//,//o
);
com_cdc_pulse zr_com_cdc_pulse_clr_ack_s2d(
    .iclk      ( clk_s        ),  //i
    .irst_n    ( rst_src_sync ),  //i
    .ipulse    ( clear_req_d2s),  //i
    .oclk      ( clk_d        ),  //i
    .orst_n    ( rst_dst_sync ),  //i
    .opulse    ( clear_ack_s2d)//,//o
);

wire clrs = clear_s || rc_src_clr_ongoing || clear_req_d2s;
wire clrd = clear_d || rc_dst_clr_ongoing || clear_req_s2d;

//0:sync_wr_rst_n, 1:sync_wr_clear, 2:sync_rd_rst_n, 3:sync_rd_clear;
assign wr_reset_signals = {clrs,rst_src_sync};
assign rd_reset_signals = {clrd,rst_dst_sync};

//wrcnt
wire [AW-0:0] wrcnt_p1  = rc_wrcnt[AW-1:0] + 1'b1; //spyglass disable W164b
wire [AW-0:0] wrcnt_nxt_t = wrcnt_p1==DEPTH_P2[AW-0:0] ? { !rc_wrcnt[AW],{AW{1'b0}} } : {rc_wrcnt[AW],wrcnt_p1[AW-1:0]};
wire [AW-0:0] wrcnt_nxt = wrcnt_nxt_t[AW-1:0]==depth_jump ? wrcnt_nxt_t+depth_comp : wrcnt_nxt_t;
wire [AW-0:0] wrcnt_gray= F_bin2gray(wrcnt_nxt);
always @(posedge clk_s or negedge rst_src_sync)
begin
    if( !rst_src_sync ) begin
        rc_wrcnt <= 'b0;
        rc_wrcnt_gray <= 'b0;
    end
    else if( clrs ) begin
        rc_wrcnt <= 'b0;
        rc_wrcnt_gray <= 'b0;
    end
    else if( afifo_wr_en && !afifo_wr_full ) begin
        rc_wrcnt <= wrcnt_nxt;
        rc_wrcnt_gray <= wrcnt_gray;
    end
end

//cross domain rd2wr
wire [AW-0:0] wq_rdcnt_gray;
com_cdc_sig #(
    .DATA_W     ( AW+1       ) //8
)r_com_cdc_sig_r2w
(
    .oclk              ( clk_s                ), //i
    .orst_n            ( rst_src_sync         ), //i
    .idata             ( rc_rdcnt_gray        ), //i
    .odata             ( wq_rdcnt_gray        )  //o
);

//rdcnt
wire [AW-0:0] rdcnt_p1  = rc_rdcnt[AW-1:0] + 1'b1; //spyglass disable W164b
wire [AW-0:0] rdcnt_nxt_t = rdcnt_p1==DEPTH_P2[AW-0:0] ? { !rc_rdcnt[AW],{AW{1'b0}} } : {rc_rdcnt[AW],rdcnt_p1[AW-1:0]};
wire [AW-0:0] rdcnt_nxt = rdcnt_nxt_t[AW-1:0]==depth_jump ? rdcnt_nxt_t+depth_comp : rdcnt_nxt_t;
wire [AW-0:0] rdcnt_gray= F_bin2gray(rdcnt_nxt);
always @(posedge clk_d or negedge rst_dst_sync)
begin
    if( !rst_dst_sync ) begin
        rc_rdcnt <= 'b0;
        rc_rdcnt_gray <= 'b0;
    end
    else if( clrd ) begin
        rc_rdcnt <= 'b0;
        rc_rdcnt_gray <= 'b0;
    end
    else if( afifo_rd_en && !afifo_rd_empty ) begin
        rc_rdcnt <= rdcnt_nxt;
        rc_rdcnt_gray <= rdcnt_gray;
    end
end

//cross domain wr2rd
wire [AW-0:0] rq_wrcnt_gray;
com_cdc_sig #(
    .DATA_W     ( AW+1       ) //8
)r_com_cdc_sig_w2r
(
    .oclk              ( clk_d                ), //i
    .orst_n            ( rst_dst_sync         ), //i
    .idata             ( rc_wrcnt_gray        ), //i
    .odata             ( rq_wrcnt_gray        )  //o
);

//full&empty
wire [AW-0:0] wq_rdcnt_bin = F_gray2bin(wq_rdcnt_gray);
wire [AW-0:0] rq_wrcnt_bin = F_gray2bin(rq_wrcnt_gray);
assign afifo_wr_full = (rc_wrcnt[AW-1:0]==wq_rdcnt_bin[AW-1:0]) && (rc_wrcnt[AW]==!wq_rdcnt_bin[AW]);//wr domain
assign afifo_rd_empty= (rc_rdcnt[AW-0:0]==rq_wrcnt_bin[AW-0:0]);//rd domain

//water level in wr domain
wire [AW-0:0] wq_rdcnt_bin_s = wq_rdcnt_bin[AW-1:0]>=depth_jump ? wq_rdcnt_bin-depth_comp : wq_rdcnt_bin;
wire [AW-0:0] wrcnt_s = rc_wrcnt[AW-1:0]>=depth_jump ? rc_wrcnt-depth_comp : rc_wrcnt;
wire [AW-0:0] minus = {1'b0,wq_rdcnt_bin_s[AW-1:0]} - {1'b0,wrcnt_s[AW-1:0]};
wire [AW-0:0] comp  = $signed(minus) + $signed({1'b0,DEPTH[AW-0:0]});
wire [AW-0:0]    wl = (wrcnt_s[AW]==wq_rdcnt_bin_s[AW]) ? comp : minus;

//out---
//src_clk domain---
assign wr_full  = afifo_wr_full;
assign wr_addr  = wrcnt_s;
assign water_level = wl;
//dst_clk domain---
wire [AW-0:0] rdcnt_s = rc_rdcnt[AW-1:0]>=depth_jump ? rc_rdcnt-depth_comp : rc_rdcnt;
assign rd_empty = afifo_rd_empty;
assign rd_addr  = rdcnt_s;

//function--------------------------------------------------------------------
function  [AW-0:0] F_bin2gray;
input [AW-0:0]    bin;
reg   [AW-1:0]    gray;
begin
    gray = bin[AW-1:0] ^ (bin[AW-1:0]>>1);
    F_bin2gray = {bin[AW],gray};
end
endfunction

function  [AW-0:0] F_gray2bin;
input [AW-0:0]    gray;
reg   [AW-0:0]    bin;
begin
    bin[AW] = gray[AW];
    //gray to binary
    bin[AW-1] = gray[AW-1];
    for( int i=1; i<AW; i++ )
        bin[AW-1-i] = bin[AW-i] ^ gray[AW-1-i];

    F_gray2bin = bin;
end
endfunction

//assert--------------------------------------------------------------------
`COM_SIGNAL_ASSERT( a0, wr_clk,wr_rst_n,wr_en,!wr_full , "aync_fifo write when full" );
`COM_SIGNAL_ASSERT( a1, rd_clk,rd_rst_n,rd_en,!rd_empty, "aync_fifo read when empty" );

endmodule //end of com_async_fifo_ctrl
`endif //end of com_async_fifo_ctrl_v

