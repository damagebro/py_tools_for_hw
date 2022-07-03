/******************************************************************************
*
*  Authors:   dmg
*    Email:   dmg@sensetime.com
*     Date:   2019/11/25-11:01:51
*
*  Description:
*   ahb lite bus transform to csr bus;
*
*  Modify:
*  -
*
******************************************************************************/

`ifndef com_csr_ahbl2csr_v
`define com_csr_ahbl2csr_v
module com_csr_ahbl2csr #( parameter
    AW_AHB = 32,
    DW_AHB = 32,
    AW_CSR = 16,
    DW_CSR = 32,
    SW_CSR = DW_CSR/8
)
(
input  wire                     HCLK                ,
input  wire                     HRESETn             ,

input  wire                     HSELx               ,
input  wire                     HREADY              ,
input  wire [AW_AHB-1:0]        HADDR               ,
input  wire [1:0]               HTRANS              ,//0:idle, 1:busy, 2:nonseq, 3:seq
input  wire                     HWRITE              ,
input  wire [2:0]               HSIZE               ,//bytelen = 2^size
input  wire [2:0]               HBURST              ,//0:single, 1:incr
input  wire [3:0]               HPROT               ,
input  wire [DW_AHB-1:0]        HWDATA              ,

output wire [DW_AHB-1:0]        HRDATA              ,
output wire                     HREADYOUT           ,
output wire                     HRESP               ,//0: OKAY, 1:ERROR

com_csr_if.master               csr_txif            //,
);
//localparam-----------------------------------------------------------------
localparam LG2_SW_CSR = $clog2(SW_CSR>2?SW_CSR:2);

localparam HT_IDLE   = 2'b00,
           HT_BUSY   = 2'b01,
           HT_NONSEQ = 2'b10,
           HT_SEQ    = 2'b11;
localparam HB_SINGLE = 3'b000,
           HB_INCR   = 3'b001;
localparam HR_OKAY   = 1'b0,
           HR_ERROR  = 1'b1;
//reg  declare---------------------------------------------------------------
reg  rc_ahberr_flag;
reg  rc_ahberr_cnt;
//wire declare---------------------------------------------------------------
wire clk   = HCLK;
wire rst_n = HRESETn;
wire [AW_AHB-1:0] ahb_baseaddr = 32'h0000_0000;

wire                   csr_write      ;
wire [AW_CSR-1:0]      csr_addr       ;
wire [DW_CSR-1:0]      csr_wdata      ;
wire [SW_CSR-1:0]      csr_wstrb      ;
wire                   csr_valid      ;
wire                   csr_ready      ;
wire [DW_CSR-1:0]      csr_rdata      ;
assign csr_txif.csr_write  = csr_write ;
assign csr_txif.csr_addr   = csr_addr  ;
assign csr_txif.csr_wdata  = csr_wdata ;
assign csr_txif.csr_wstrb  = csr_wstrb ;
assign csr_txif.csr_valid  = csr_valid ;
assign csr_ready   = csr_txif.csr_ready;
assign csr_rdata   = csr_txif.csr_rdata;
//statement------------------------------------------------------------------
reg  rc_ahbbusy_flag;
reg  rc_csrrd_flag;
wire hin_valid = rc_ahberr_flag ? 1'b0 : HSELx && HREADY && HTRANS[1]==1;//HTRANS==HT_NONSEQ || HTRANS==HT_SEQ;
wire hin_ready = csr_ready;
wire hout_valid= rc_ahbbusy_flag;
wire hout_ready= csr_ready;
wire hin_hs    = hin_valid && hin_ready;
wire hout_hs   = hout_valid&& hout_ready;
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n )begin
        rc_ahbbusy_flag <= 1'b0;
    end
    else if( hout_hs && !hin_hs )begin
        rc_ahbbusy_flag <= 1'b0;
    end
    else if( hin_hs )begin
        rc_ahbbusy_flag <= 1'b1;
    end
end
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n )begin
        rc_csrrd_flag <= 1'b0;
    end
    else if( hin_hs && !HWRITE )begin
        rc_csrrd_flag <= 1'b1;
    end
    else if( hout_hs && rc_csrrd_flag )begin
        rc_csrrd_flag <= 1'b0;
    end
end

reg  [AW_AHB-1:0] haddr_d  ;
reg  [2:0]        hsize_d  ;
reg  [1:0]        htrans_d ;
reg  [2:0]        hburst_d ;
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n )begin
        haddr_d  <= 'b0;
        hsize_d  <= 'b0;
        htrans_d <= 'b0;
        hburst_d <= 'b0;
    end
    else if( hin_hs )begin
        haddr_d  <= HADDR ;
        hsize_d  <= HSIZE ;
        htrans_d <= HTRANS;
        hburst_d <= HBURST;
    end
end
assign csr_valid  = hout_valid;
assign csr_write = !rc_csrrd_flag;

wire [AW_AHB-1:0] haddr_off0 = haddr_d - ahb_baseaddr;
assign csr_addr   = SW_CSR==1 ? haddr_off0[AW_CSR-1:0] : { haddr_off0[AW_CSR-1:LG2_SW_CSR],{LG2_SW_CSR{1'b0}} };
assign csr_wdata = DW_CSR'(HWDATA);
assign csr_wstrb = SW_CSR==1 ? 1'b1 : (rc_csrrd_flag || haddr_off0[LG2_SW_CSR-1:0]==LG2_SW_CSR'(0)) ? {SW_CSR{1'b1}} : ((1<<hsize_d)-1)<<haddr_off0[LG2_SW_CSR-1:0];
// wire [LG2_SW_CSR-1:0] haddr_lsb = haddr_off0[LG2_SW_CSR-1:0];
// wire [SW_CSR-1:0] t1_csrwrstrb = (1<<HSIZE)-1);
// wire [SW_CSR-1:0] t2_csrwrstrb = t1_csrwrstrb<<haddr_lsb;
// assign CSRWrStrb = SW_CSR==1 ? 1'b1 : (rc_csrrd_flag || haddr_lsb==LG2_SW_CSR'(0)) ? {SW_CSR{1'b1}} : t2_csrwrstrb;

assign HREADYOUT = rc_ahberr_flag ? rc_ahberr_cnt : rc_ahbbusy_flag ? csr_ready : 1'b1;
assign HRDATA    = DW_AHB'(csr_rdata);
assign HRESP     = rc_ahberr_flag;

//deal err,
//(1)HBURST==HB_SINGLE || HBURST==HB_INCR, only;
//(2)HTRANS==SEQ, addr increasement incorrect;
//(3)HSIZE, larger than $clog2(SW_CSR);
wire hvalid = HSELx && HREADY;
wire hburst_err = hvalid && !(HBURST==HB_SINGLE || HBURST==HB_INCR);
wire htrans_err = hvalid && HTRANS==HT_SEQ && HADDR!=haddr_d+(1<<hsize_d);//TBD
wire hsize_err  = hvalid && HSIZE>$clog2(SW_CSR);
wire cond_ok = rc_ahberr_flag && rc_ahberr_cnt==1'b1;
wire cond_err= hburst_err || htrans_err || hsize_err;
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n )begin
        rc_ahberr_flag <= 1'b0;
    end
    else if( cond_ok )begin
        rc_ahberr_flag <= 1'b0;
    end
    else if( cond_err )begin
        rc_ahberr_flag <= 1'b1;
    end
end
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n )begin
        rc_ahberr_cnt <= 'b0;
    end
    else if( cond_ok )begin
        rc_ahberr_cnt <= 'b0;
    end
    else if( rc_ahberr_flag )begin
        rc_ahberr_cnt <= rc_ahberr_cnt + 1'b1;
    end
end

endmodule //end of com_csr_ahbl2csr
`endif //end of com_csr_ahbl2csr_v

