/******************************************************************************
*
*  Authors:   dmg
*    Email:   dmg@sensetime.com
*     Date:   2019/11/25-14:35:32
*
*  Description:
*  -
*
*  Modify:
*   2021/11/30: only 1 async_fifo from src to dst;
*               only 1 async_fifo from dst to src;
*
******************************************************************************/

//`include "com_asyncfifo_reg.v"

`ifndef com_csr_cdc_v
`define com_csr_cdc_v
module com_csr_cdc #( parameter
    AW = 16,
    DW = 32,
    SW = DW/8
)
(
input  wire                     clk_s               ,
input  wire                     rst_n_s             ,
input  wire                     clear_s             ,
input  wire                     clk_d               ,
input  wire                     rst_n_d             ,
input  wire                     clear_d             ,

com_csr_if.slave                csr_rxif            ,
com_csr_if.master               csr_txif             //,
);
//localparam-----------------------------------------------------------------
localparam AFIFO_DEPTH_S2D = 8;
localparam AFIFO_DEPTH_D2S = 2;
//reg  declare---------------------------------------------------------------
//wire declare---------------------------------------------------------------
wire                   rx_csr_write      ;
wire [AW-1:0]          rx_csr_addr       ;
wire [DW-1:0]          rx_csr_wdata      ;
wire [SW-1:0]          rx_csr_wstrb      ;
wire                   rx_csr_valid      ;
wire                   rx_csr_ready      ;
wire [DW-1:0]          rx_csr_rdata      ;

wire                   tx_csr_write      ;
wire [AW-1:0]          tx_csr_addr       ;
wire [DW-1:0]          tx_csr_wdata      ;
wire [SW-1:0]          tx_csr_wstrb      ;
wire                   tx_csr_valid      ;
wire                   tx_csr_ready      ;
wire [DW-1:0]          tx_csr_rdata      ;

assign rx_csr_write  = csr_rxif.csr_write ;
assign rx_csr_addr   = csr_rxif.csr_addr  ;
assign rx_csr_wdata  = csr_rxif.csr_wdata ;
assign rx_csr_wstrb  = csr_rxif.csr_wstrb ;
assign rx_csr_valid  = csr_rxif.csr_valid ;
assign csr_rxif.csr_ready   = rx_csr_ready ;
assign csr_rxif.csr_rdata   = rx_csr_rdata ;

assign csr_txif.csr_write  = tx_csr_write ;
assign csr_txif.csr_addr   = tx_csr_addr  ;
assign csr_txif.csr_wdata  = tx_csr_wdata ;
assign csr_txif.csr_wstrb  = tx_csr_wstrb ;
assign csr_txif.csr_valid  = tx_csr_valid ;
assign tx_csr_ready   = csr_txif.csr_ready ;
assign tx_csr_rdata   = csr_txif.csr_rdata ;
//statement------------------------------------------------------------------
reg  rc_csr_rdflag;
always @(posedge clk_s or negedge rst_n_s)
begin
    if( !rst_n_s )begin
        rc_csr_rdflag <= 1'b0;
    end
    else if( clear_s || (rx_csr_valid&&rx_csr_ready) )begin
        rc_csr_rdflag <= 1'b0;
    end
    else if( rx_csr_valid && !rx_csr_write )begin
        rc_csr_rdflag <= 1'b1;
    end
end

wire                     awr_en     = rx_csr_write ? rx_csr_valid && rx_csr_ready : rx_csr_valid && !rc_csr_rdflag;
wire [SW+DW+AW+1-1:0]    awr_data   = {rx_csr_wstrb,rx_csr_wdata,rx_csr_addr,rx_csr_write};
wire                     ard_en     ;
wire [SW+DW+AW+1-1:0]    ard_data   ;
wire                     awr_full   ;
wire                     ard_empty  ;
com_async_fifo_reg #(
    .DW         ( SW+DW+AW+1      ), //8
    .DEPTH      ( AFIFO_DEPTH_S2D )  //4
)r_com_async_fifo_reg_s2d
(
    .wr_clk               ( clk_s                ), //i
    .wr_rst_n             ( rst_n_s              ), //i
    .wr_clear             ( clear_s              ), //i
    .rd_clk               ( clk_d                ), //i
    .rd_rst_n             ( rst_n_d              ), //i
    .rd_clear             ( clear_d              ), //i

    .wr_en                ( awr_en               ), //i
    .wr_data              ( awr_data             ), //i
    .wr_full              ( awr_full             ), //o
    .rd_en                ( ard_en               ), //i
    .rd_data              ( ard_data             ), //o
    .rd_empty             ( ard_empty            ), //o
    .water_level          (                      )  //o
);
assign ard_en = tx_csr_valid && tx_csr_ready;
assign tx_csr_valid = !ard_empty;
assign {tx_csr_wstrb,tx_csr_wdata,tx_csr_addr,tx_csr_write} = ard_data;

wire                     rd_wr_en    = tx_csr_valid && tx_csr_ready && !tx_csr_write;
wire [DW-1:0]            rd_wr_data  = tx_csr_rdata;
wire                     rd_rd_en    ;
wire [DW-1:0]            rd_rd_data  ;
wire                     rd_wr_full  ;
wire                     rd_rd_empty ;
com_async_fifo_reg #(
    .DW         ( DW              ), //8
    .DEPTH      ( AFIFO_DEPTH_D2S )  //4
)r_com_async_fifo_reg_d2s
(
    .wr_clk               ( clk_d                ), //i
    .wr_rst_n             ( rst_n_d              ), //i
    .wr_clear             ( clear_d              ), //i
    .rd_clk               ( clk_s                ), //i
    .rd_rst_n             ( rst_n_s              ), //i
    .rd_clear             ( clear_s              ), //i

    .wr_en                ( rd_wr_en             ), //i
    .wr_data              ( rd_wr_data           ), //i
    .rd_en                ( rd_rd_en             ), //i
    .rd_data              ( rd_rd_data           ), //o
    .wr_full              ( rd_wr_full           ), //o
    .rd_empty             ( rd_rd_empty          ), //o
    .water_level          (                      )  //o
);
assign rd_rd_en = !rd_rd_empty;
assign rx_csr_ready = rx_csr_write ? !awr_full : !rd_rd_empty;
assign rx_csr_rdata = rd_rd_data;

endmodule //end of com_csr_cdc
`endif //end of com_csr_cdc_v

