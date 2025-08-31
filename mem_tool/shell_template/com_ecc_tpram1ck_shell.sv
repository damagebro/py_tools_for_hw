/******************************************************************************
*
*  Authors:   wwq,dmg
*    Email:   dmg@sensetime.com
*     Date:   2025/07/07-20:01:49
*
*  Description:
*  -
*
*  Modify:
*  -
*
******************************************************************************/

module com_ecc_tpram1ck_shell#(
parameter  DATA_W   = 32           , //range=[4:8178], Data width of memory.
parameter  DEPTH    = 64           , //range=[1:], Depth of memory.
parameter  STRB_W   = 1            , //range=[1:DATA_W], assert(DEPTH%STRB_W==0);  partial_write strobe width,  //assume DATA_W=30bit, STRB_W=2; so => strb[1:0]=2bit, strb[0]->wdata[0*15 +:15], strb[1]->wdata[1*15 +:15];
parameter  MEM_USER = 0            , //range=[0:], Memory user diy

parameter  REQ_PIPE = 0            , //range=[0:1], raddr + wdata/waddr insert regslice "before access sram_lib and after ecc_encode";
parameter  RSP_PIPE = 0            , //range=[0:1], rdata insert regslice "after access sram_lib and before ecc_decode";
parameter  ECC_DW   = DATA_W/STRB_W, //range=[8:DATA_W:STRB_W==1?any:DATA_W/STRB_W]; SUB_DW=DATA_W/STRB_W, assert(STRB_W==1 || (SUB_DW%ECC_DW==0));
localparam ADDR_W   = $clog2(DEPTH)  // Address width,
)(
input  wire                   clk           ,
input  wire [`COM_SYS_W-1:0]  sys_cfg       ,  //[0]ecc_correct enbale, [1]ecc_inject_error enable, [3:2]ecc_inject_error val;

input  wire [STRB_W-1:0]      wr_en         , //assume DATA_W=30bit, STRB_W=2; so => wr_en[1:0]=2bit, wr_en[0]->wdata[0*15 +:15], wr_en[1]->wdata[1*15 +:15];
input  wire [ADDR_W-1:0]      wr_addr       ,
input  wire [DATA_W-1:0]      wr_data       ,
input  wire                   rd_en         ,
input  wire [ADDR_W-1:0]      rd_addr       ,
output wire [DATA_W-1:0]      rd_data       ,
output wire [1:0]             o_pls_ecc_err //,  //[0]=ce(correctable error), ecc_error_bits=1bit; [1]=ue(uncorrectable error), ecc_error_bits>=2bit;
);
//localparam-----------------------------------------------------------------
localparam SUB_DW  = DATA_W/STRB_W;  //each strb_w[bit_idx] ctrl sub_data_width;
`COM_PARAM_ASSERT(STRB_W==1 || (SUB_DW%ECC_DW==0), "if STRB_W>1, (DATA_W/STRB_W)%%ECC_DW must be zero;");
`COM_PARAM_ASSERT((DATA_W>=4 && DATA_W<=8178), "ecc_ram data_bit_width range=[4:8178]");

localparam NRM_ORI_W   = ECC_DW;  //ori_ram_data_width
localparam NRM_ECC_W   = F_lut_ecc_width(NRM_ORI_W); //ecc addtion from ori_ram_data_width;
localparam NRM_ECC_NUM = DATA_W/ECC_DW;
localparam NRM_TOL_W   = NRM_ORI_W*NRM_ECC_NUM;
localparam LST_ORI_W   = DATA_W%ECC_DW;
localparam LST_ECC_W   = LST_ORI_W>0 ? F_lut_ecc_width(LST_ORI_W) : 0;
localparam LST_ECC_NUM = LST_ORI_W>0 ? 1 : 0;
localparam TOL_RAM_W = DATA_W + NRM_ECC_W*NRM_ECC_NUM+LST_ECC_W*LST_ECC_NUM;  //{lst_ecc_data,nrm_ecc_data*n,ori_ram_data};

function automatic int F_lut_ecc_width( int ori_bit_width );  //only for parameter calc
    int ret;
    ret = ori_bit_width<=11   ? 5  :       // [4   :11  ]    5   ;
          ori_bit_width<=26   ? 6  :       // [12  :26  ]    6   ;
          ori_bit_width<=57   ? 7  :       // [27  :57  ]    7   ;
          ori_bit_width<=120  ? 8  :       // [58  :120 ]    8   ;
          ori_bit_width<=247  ? 9  :       // [121 :247 ]    9   ;
          ori_bit_width<=502  ? 10 :       // [248 :502 ]    10  ;
          ori_bit_width<=1013 ? 11 :       // [503 :1013]    11  ;
          ori_bit_width<=2036 ? 12 :       // [1014:2036]    12  ;
          ori_bit_width<=4083 ? 13 :       // [2037:4083]    13  ;
          ori_bit_width<=8178 ? 14 : 15;   // [4084:8178]    14  ;
    return ret;
endfunction:F_lut_ecc_width
//signal declare-------------------------------------------------------------
wire [TOL_RAM_W-1:0]                   w_ram_wr_data  ;
wire [TOL_RAM_W-1:0]                   w_ram_rd_data  ;

wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0]  u_nrm_ori_wr_data;
wire [NRM_ECC_NUM-1:0][NRM_ECC_W-1:0]  u_nrm_ecc_wr_data;
wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0]  u_nrm_ori_rd_data;
wire [NRM_ECC_NUM-1:0][NRM_ECC_W-1:0]  u_nrm_ecc_rd_data;
wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0]  u_nrm_crt_rd_data; //correct
wire [STRB_W-1:0]     u_ram_wr_en    ;
wire [ADDR_W-1:0]     u_ram_wr_addr  ;
wire [TOL_RAM_W-1:0]  u_ram_wr_data  ;
wire                  u_ram_rd_en    ;
wire [ADDR_W-1:0]     u_ram_rd_addr  ;
wire [TOL_RAM_W-1:0]  u_ram_rd_data  ;
// generate if( REQ_PIPE )begin end endgenerate
// generate if( RSP_PIPE )begin end endgenerate
//statement------------------------------------------------------------------

wire       i_cfg_ecc_correct_en = sys_cfg[0];
wire       i_cfg_ecc_inject_en  = sys_cfg[1];
wire [1:0] i_cfg_ecc_inject_val = sys_cfg[3:2];
wire [DATA_W-1:0] wr_data_t = i_cfg_ecc_inject_en ? {wr_data[DATA_W-1:2], wr_data[1:0]^i_cfg_ecc_inject_val[1:0]} : wr_data;
//#nrm_ecc---------------------------------------------------------------------------------
assign o_pls_ecc_err = '0;

//1. ecc_enc/ecc_dec-----
assign u_nrm_ori_wr_data = wr_data_t[NRM_TOL_W-1:0];
assign u_nrm_ecc_wr_data = '0;  //TBD
assign u_nrm_crt_rd_data = u_nrm_ori_rd_data;  //TBD
// DW_ecc #(
//     .DW  (NRM_ORI_W)
// )u_dw_ecc_enc_nrm[NRM_ECC_NUM-1:0]
// (
//     .i_original_data (u_nrm_ori_wr_data  ),  //i
//     .i_ecc_dec_data  ('0                 ),  //i
//     .o_correct_data  ('0                 ),  //o
//     .o_ecc_enc_data  (u_nrm_ecc_wr_data  )   //o
// );
// DW_ecc #(
//     .DW  (NRM_ORI_W)
// )u_dw_ecc_dec_nrm[NRM_ECC_NUM-1:0]
// (
//     .i_original_data (u_nrm_ori_rd_data  ),  //i
//     .i_ecc_dec_data  (u_nrm_ecc_rd_data  ),  //i
//     .o_correct_data  (u_nrm_crt_rd_data  ),  //o
//     .o_ecc_enc_data  (                   )   //o
// );
generate
if( LST_ECC_NUM )begin:gen_lst_ecc
    wire [LST_ORI_W-1:0]  u_lst_ori_wr_data;
    wire [LST_ECC_W-1:0]  u_lst_ecc_wr_data;
    wire [LST_ORI_W-1:0]  u_lst_ori_rd_data;
    wire [LST_ECC_W-1:0]  u_lst_ecc_rd_data;
    wire [LST_ORI_W-1:0]  u_lst_crt_rd_data; //correct
    assign rd_data = {u_lst_crt_rd_data,u_nrm_crt_rd_data};
    assign w_ram_wr_data = {u_lst_ecc_wr_data,u_nrm_ecc_wr_data, u_lst_ori_wr_data,u_nrm_ori_wr_data};
    assign {u_lst_ecc_rd_data,u_nrm_ecc_rd_data, u_lst_ori_rd_data,u_nrm_ori_rd_data} = w_ram_rd_data;
    assign u_lst_ori_wr_data = wr_data_t[NRM_TOL_W +:LST_ORI_W];
    assign u_lst_ecc_wr_data = '0;  //TBD
    assign u_lst_crt_rd_data = u_lst_ori_rd_data;  //TBD
    // DW_ecc #(
    //     .DW  (LST_ECC_DW)
    // )u_dw_ecc_enc_lst
    // (
    //     .i_original_data (u_lst_ori_wr_data  ),  //i
    //     .i_ecc_dec_data  ('0                 ),  //i
    //     .o_correct_data  ('0                 ),  //o
    //     .o_ecc_enc_data  (u_lst_ecc_wr_data  )   //o
    // );
    // DW_ecc #(
    //     .DW  (LST_ECC_DW)
    // )u_dw_ecc_dec_lst
    // (
    //     .i_original_data (u_lst_ori_rd_data  ),  //i
    //     .i_ecc_dec_data  (u_lst_ecc_rd_data  ),  //i
    //     .o_correct_data  (u_lst_crt_rd_data  ),  //o
    //     .o_ecc_enc_data  (                   )   //o
    // );
end:gen_lst_ecc
else begin
    assign rd_data = {u_nrm_crt_rd_data};
    assign w_ram_wr_data = {u_nrm_ecc_wr_data, u_nrm_ori_wr_data};
    assign {u_nrm_ecc_rd_data, u_nrm_ori_rd_data} = w_ram_rd_data;
end
endgenerate

//2. REQ_PIPE/RSP_PIPE-----------------
generate
if( REQ_PIPE )begin
    reg  [STRB_W-1:0]     r_ram_wr_en    ;
    reg  [ADDR_W-1:0]     r_ram_wr_addr  ;
    reg  [TOL_RAM_W-1:0]  r_ram_wr_data  ;
    reg                   r_ram_rd_en    ;
    reg  [ADDR_W-1:0]     r_ram_rd_addr  ;
    assign u_ram_wr_en    = r_ram_wr_en  ;
    assign u_ram_wr_addr  = r_ram_wr_addr;
    assign u_ram_wr_data  = r_ram_wr_data;
    assign u_ram_rd_en    = r_ram_rd_en  ;
    assign u_ram_rd_addr  = r_ram_rd_addr;
    always@(posedge clk)begin
        r_ram_wr_en   <= wr_en  ;
        r_ram_wr_addr <= wr_addr;
        r_ram_wr_data <= w_ram_wr_data;
    end
    always@(posedge clk)begin
        r_ram_rd_en   <= rd_en  ;
        r_ram_rd_addr <= rd_addr;
    end
end
else begin
    assign u_ram_wr_en    = wr_en  ;
    assign u_ram_wr_addr  = wr_addr;
    assign u_ram_wr_data  = w_ram_wr_data;
    assign u_ram_rd_en    = rd_en  ;
    assign u_ram_rd_addr  = rd_addr;
end
endgenerate
generate
if( RSP_PIPE )begin
    reg  [TOL_RAM_W-1:0]  r_ram_rd_data;
    assign w_ram_rd_data  = r_ram_rd_data;
    always@(posedge clk)begin
        r_ram_rd_data <= u_ram_rd_data;
    end
end
else begin
    assign w_ram_rd_data  = u_ram_rd_data;
end
endgenerate

//3. sram_shell-----
com_tpram1ck_shell #(
    .DATA_W               ( TOL_RAM_W           ), //32
    .DEPTH                ( DEPTH               ), //64
    .STRB_W               ( STRB_W              ), //1
    .MEM_USER             ( MEM_USER            )  //0
)u_com_tpram1ck_shell
(
    .clk                 ( clk                  ), //i
    .sys_cfg             ( sys_cfg              ), //i
    .wr_en               ( u_ram_wr_en          ), //i
    .wr_addr             ( u_ram_wr_addr        ), //i
    .wr_data             ( u_ram_wr_data        ), //i
    .rd_en               ( u_ram_rd_en          ), //i
    .rd_addr             ( u_ram_rd_addr        ), //i
    .rd_data             ( u_ram_rd_data        )  //o
);

endmodule
