"""Generated RTL strings. Run get_rtl_template.py after editing rtl/shell."""

# This file is generated. Do not edit it directly.
RTL_TEMPLATES: dict[str, str] = {
    "com_ecc_spram_shell.sv": r"""/******************************************************************************
*
*  Authors:   wwq,dmg
*    Email:   dmg@sensetime.com
*     Date:   2025/07/07-20:01:49
*
*  Description:
*  - SECDED protected single-port SRAM implementation shell.
*
******************************************************************************/

module com_ecc_spram_shell #( parameter
    DATA_W   = 32,              //range=[4:8178:]
    DEPTH    = 64,              //range=[1::]
    STRB_W   = 1,               //range=[1:DATA_W:]
    MEM_USER = 0,
    REQ_PIPE = 0,               //range=[0:1:]
    RSP_PIPE = 0,               //range=[0:1:]
    ECC_DW   = DATA_W,          //range=[4:DATA_W:]
    localparam ADDR_W = $clog2(DEPTH)
)
(
input  wire                         clk                 ,
input  wire [`COM_MEM_CTRL_W-1:0]   i_cfg_mem_ctrl      ,
input  wire [`COM_ECC_CTRL_W-1:0]   i_cfg_ecc_ctrl      , //[0]correct_n, [1]inject_en, [3:2]inject_val

input  wire                         i_ce_n              ,
input  wire [STRB_W-1:0]            i_we_n              , //0: write, 1: read
input  wire [ADDR_W-1:0]            i_addr              ,
input  wire [DATA_W-1:0]            i_wr_data           ,
output wire [DATA_W-1:0]            o_rd_data           ,
output wire [1:0]                   o_pls_ecc_err       //,
);
//localparam-----------------------------------------------------------------
localparam NRM_ORI_W     = ECC_DW;
localparam NRM_ECC_W     = F_lut_ecc_width(NRM_ORI_W);
localparam NRM_ECC_NUM   = DATA_W/ECC_DW;
localparam NRM_TOL_W     = NRM_ORI_W*NRM_ECC_NUM;
localparam LST_ORI_W     = DATA_W%ECC_DW;
localparam LST_ECC_W     = LST_ORI_W>0 ? F_lut_ecc_width(LST_ORI_W) : 0;
localparam LST_ECC_NUM   = LST_ORI_W>0;
localparam LST_SAFE_W    = LST_ORI_W>=4 ? LST_ORI_W : 4;
localparam LST_SAFE_ECC_W = F_lut_ecc_width(LST_SAFE_W);
localparam SUB_DW        = DATA_W/STRB_W;
// One RAM row stores one partial-write flag, DATA_W original bits and all SECDED check bits.
// nrm: NRM_ECC_NUM complete ECC words, each with NRM_ORI_W data bits and NRM_ECC_W check bits.
// lst: optional last ECC word with LST_ORI_W data bits and LST_ECC_W check bits.
// Storage order: {partial_write_flag,lst_ecc,nrm_ecc,original_data}.
localparam TOL_RAM_W     = 1+DATA_W+NRM_ECC_W*NRM_ECC_NUM+LST_ECC_W*LST_ECC_NUM;
localparam RD_VLD_DELAY  = 1+REQ_PIPE+RSP_PIPE;

function automatic int F_lut_ecc_width( int ori_bit_width );
    int ret;
    ret = ori_bit_width<=11   ? 5  :
          ori_bit_width<=26   ? 6  :
          ori_bit_width<=57   ? 7  :
          ori_bit_width<=120  ? 8  :
          ori_bit_width<=247  ? 9  :
          ori_bit_width<=502  ? 10 :
          ori_bit_width<=1013 ? 11 :
          ori_bit_width<=2036 ? 12 :
          ori_bit_width<=4083 ? 13 : 14;
    return ret;
endfunction:F_lut_ecc_width

//signal declare-------------------------------------------------------------
reg  [RD_VLD_DELAY-1:0] r_rd_vld_pipe;

wire                   cfg_ecc_correct_n;
wire                   cfg_ecc_inject_en;
wire [1:0]             cfg_ecc_inject_val;
wire                   rd_req;
wire [STRB_W-1:0]      wr_en;
wire                   wr_req;
wire                   full_write;
wire                   partial_write;
wire                   rd_partial_write_flag;
wire [DATA_W-1:0]      wr_data_inj;
wire [DATA_W-1:0]      stored_rd_data;
wire [DATA_W-1:0]      correct_rd_data;
wire [TOL_RAM_W-1:0]   ecc_ram_wr_data;
wire [TOL_RAM_W-1:0]   ecc_ram_rd_data;
wire [TOL_RAM_W-1:0]   ram_wr_bit_en;
wire                   ecc_ce;
wire                   ecc_ue;

wire                   u_ram_i_ce_n;
wire [TOL_RAM_W-1:0]   u_ram_i_we_n;
wire [ADDR_W-1:0]      u_ram_i_addr;
wire [TOL_RAM_W-1:0]   u_ram_i_wr_data;
wire [TOL_RAM_W-1:0]   u_ram_o_rd_data;

wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0] u_nrm_enc_i_original_data;
wire [NRM_ECC_NUM-1:0][NRM_ECC_W-1:0] u_nrm_enc_i_ecc_dec_data;
wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0] u_nrm_enc_o_correct_data;
wire [NRM_ECC_NUM-1:0][NRM_ECC_W-1:0] u_nrm_enc_o_ecc_enc_data;
wire [NRM_ECC_NUM-1:0]                u_nrm_enc_o_ecc_ce;
wire [NRM_ECC_NUM-1:0]                u_nrm_enc_o_ecc_ue;
wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0] u_nrm_dec_i_original_data;
wire [NRM_ECC_NUM-1:0][NRM_ECC_W-1:0] u_nrm_dec_i_ecc_dec_data;
wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0] u_nrm_dec_o_correct_data;
wire [NRM_ECC_NUM-1:0][NRM_ECC_W-1:0] u_nrm_dec_o_ecc_enc_data;
wire [NRM_ECC_NUM-1:0]                u_nrm_dec_o_ecc_ce;
wire [NRM_ECC_NUM-1:0]                u_nrm_dec_o_ecc_ue;

wire [LST_SAFE_W-1:0]     u_lst_enc_i_original_data;
wire [LST_SAFE_ECC_W-1:0] u_lst_enc_i_ecc_dec_data;
wire [LST_SAFE_W-1:0]     u_lst_enc_o_correct_data;
wire [LST_SAFE_ECC_W-1:0] u_lst_enc_o_ecc_enc_data;
wire                      u_lst_enc_o_ecc_ce;
wire                      u_lst_enc_o_ecc_ue;
wire [LST_SAFE_W-1:0]     u_lst_dec_i_original_data;
wire [LST_SAFE_ECC_W-1:0] u_lst_dec_i_ecc_dec_data;
wire [LST_SAFE_W-1:0]     u_lst_dec_o_correct_data;
wire [LST_SAFE_ECC_W-1:0] u_lst_dec_o_ecc_enc_data;
wire                      u_lst_dec_o_ecc_ce;
wire                      u_lst_dec_o_ecc_ue;

//statement------------------------------------------------------------------
//output assign---
assign o_rd_data = rd_partial_write_flag ? stored_rd_data : correct_rd_data;
assign o_pls_ecc_err = r_rd_vld_pipe[RD_VLD_DELAY-1] ? {ecc_ue,ecc_ce} : '0;

//body---
assign cfg_ecc_correct_n = i_cfg_ecc_ctrl[0];
assign cfg_ecc_inject_en = i_cfg_ecc_ctrl[1];
assign cfg_ecc_inject_val = i_cfg_ecc_ctrl[3:2];
assign rd_req = !i_ce_n && (&i_we_n);
assign wr_en = {STRB_W{!i_ce_n}} & ~i_we_n;
assign wr_req = |wr_en;
assign full_write = &wr_en;
assign partial_write = wr_req && !full_write;
assign wr_data_inj = cfg_ecc_inject_en ?
                     {i_wr_data[DATA_W-1:2],i_wr_data[1:0]^cfg_ecc_inject_val} :
                     i_wr_data;

assign ecc_ce = !rd_partial_write_flag &&
                ((|u_nrm_dec_o_ecc_ce) || u_lst_dec_o_ecc_ce);
assign ecc_ue = !rd_partial_write_flag &&
                ((|u_nrm_dec_o_ecc_ue) || u_lst_dec_o_ecc_ue);

generate
for( genvar gi=0; gi<STRB_W; gi++ ) begin:gen_ram_wr_bit_en
    assign ram_wr_bit_en[gi*SUB_DW +:SUB_DW] = {SUB_DW{wr_en[gi]}};
end
endgenerate
assign ram_wr_bit_en[TOL_RAM_W-2:DATA_W] = {(TOL_RAM_W-DATA_W-1){full_write}};
assign ram_wr_bit_en[TOL_RAM_W-1] = wr_req;

always @(posedge clk) begin
    r_rd_vld_pipe[0] <= rd_req;
    for( int i=1; i<RD_VLD_DELAY; i++ )
        r_rd_vld_pipe[i] <= r_rd_vld_pipe[i-1];
end

//request pipeline
generate
if( REQ_PIPE ) begin:gen_req_pipe
    reg                    r_ram_ce_n;
    reg  [TOL_RAM_W-1:0]   r_ram_we_n;
    reg  [ADDR_W-1:0]      r_ram_addr;
    reg  [TOL_RAM_W-1:0]   r_ram_wr_data;

    assign u_ram_i_ce_n = r_ram_ce_n;
    assign u_ram_i_we_n = r_ram_we_n;
    assign u_ram_i_addr = r_ram_addr;
    assign u_ram_i_wr_data = r_ram_wr_data;
    always @(posedge clk) begin
        r_ram_ce_n <= i_ce_n;
        r_ram_we_n <= ~ram_wr_bit_en;
        r_ram_addr <= i_addr;
        r_ram_wr_data <= ecc_ram_wr_data;
    end
end
else begin:gen_req_direct
    assign u_ram_i_ce_n = i_ce_n;
    assign u_ram_i_we_n = ~ram_wr_bit_en;
    assign u_ram_i_addr = i_addr;
    assign u_ram_i_wr_data = ecc_ram_wr_data;
end
endgenerate

//response pipeline
generate
if( RSP_PIPE ) begin:gen_rsp_pipe
    reg [TOL_RAM_W-1:0] r_ram_rd_data;

    assign ecc_ram_rd_data = r_ram_rd_data;
    always @(posedge clk)
        r_ram_rd_data <= u_ram_o_rd_data;
end
else begin:gen_rsp_direct
    assign ecc_ram_rd_data = u_ram_o_rd_data;
end
endgenerate

//ECC data packing
generate
if( LST_ECC_NUM ) begin:gen_lst_pack
    assign ecc_ram_wr_data = {partial_write,u_lst_enc_o_ecc_enc_data,u_nrm_enc_o_ecc_enc_data,wr_data_inj};
    assign {rd_partial_write_flag,u_lst_dec_i_ecc_dec_data,u_nrm_dec_i_ecc_dec_data,stored_rd_data} = ecc_ram_rd_data;
    assign correct_rd_data = {u_lst_dec_o_correct_data,u_nrm_dec_o_correct_data};
end
else begin:gen_nrm_pack
    assign u_lst_dec_i_ecc_dec_data = '0;
    assign u_lst_dec_i_original_data = '0;
    assign u_lst_dec_o_ecc_ce = 1'b0;
    assign u_lst_dec_o_ecc_ue = 1'b0;
    assign ecc_ram_wr_data = {partial_write,u_nrm_enc_o_ecc_enc_data,wr_data_inj};
    assign {rd_partial_write_flag,u_nrm_dec_i_ecc_dec_data,stored_rd_data} = ecc_ram_rd_data;
    assign correct_rd_data = u_nrm_dec_o_correct_data;
end
endgenerate

//instance----
assign u_nrm_enc_i_original_data = i_wr_data[NRM_TOL_W-1:0];
assign u_nrm_enc_i_ecc_dec_data = '0;
com_ecc_secded #(
    .DW ( NRM_ORI_W )
)u_com_ecc_secded_nrm_enc[NRM_ECC_NUM-1:0]
(
    .i_correct_n     ( 1'b1                         ), //i
    .i_original_data ( u_nrm_enc_i_original_data     ), //i
    .i_ecc_dec_data  ( u_nrm_enc_i_ecc_dec_data      ), //i
    .o_correct_data  ( u_nrm_enc_o_correct_data      ), //o
    .o_ecc_enc_data  ( u_nrm_enc_o_ecc_enc_data      ), //o
    .o_ecc_ce        ( u_nrm_enc_o_ecc_ce            ), //o
    .o_ecc_ue        ( u_nrm_enc_o_ecc_ue            )  //o
);

assign u_nrm_dec_i_original_data = stored_rd_data[NRM_TOL_W-1:0];
com_ecc_secded #(
    .DW ( NRM_ORI_W )
)u_com_ecc_secded_nrm_dec[NRM_ECC_NUM-1:0]
(
    .i_correct_n     ( cfg_ecc_correct_n             ), //i
    .i_original_data ( u_nrm_dec_i_original_data     ), //i
    .i_ecc_dec_data  ( u_nrm_dec_i_ecc_dec_data      ), //i
    .o_correct_data  ( u_nrm_dec_o_correct_data      ), //o
    .o_ecc_enc_data  ( u_nrm_dec_o_ecc_enc_data      ), //o
    .o_ecc_ce        ( u_nrm_dec_o_ecc_ce            ), //o
    .o_ecc_ue        ( u_nrm_dec_o_ecc_ue            )  //o
);

generate
if( LST_ECC_NUM ) begin:gen_lst_ecc
    assign u_lst_enc_i_original_data = i_wr_data[NRM_TOL_W +:LST_SAFE_W];
    assign u_lst_enc_i_ecc_dec_data = '0;
    assign u_lst_dec_i_original_data = stored_rd_data[NRM_TOL_W +:LST_SAFE_W];

    com_ecc_secded #(
        .DW ( LST_SAFE_W )
    )u_com_ecc_secded_lst_enc
    (
        .i_correct_n     ( 1'b1                       ), //i
        .i_original_data ( u_lst_enc_i_original_data   ), //i
        .i_ecc_dec_data  ( u_lst_enc_i_ecc_dec_data    ), //i
        .o_correct_data  ( u_lst_enc_o_correct_data    ), //o
        .o_ecc_enc_data  ( u_lst_enc_o_ecc_enc_data    ), //o
        .o_ecc_ce        ( u_lst_enc_o_ecc_ce          ), //o
        .o_ecc_ue        ( u_lst_enc_o_ecc_ue          )  //o
    );

    com_ecc_secded #(
        .DW ( LST_SAFE_W )
    )u_com_ecc_secded_lst_dec
    (
        .i_correct_n     ( cfg_ecc_correct_n           ), //i
        .i_original_data ( u_lst_dec_i_original_data   ), //i
        .i_ecc_dec_data  ( u_lst_dec_i_ecc_dec_data    ), //i
        .o_correct_data  ( u_lst_dec_o_correct_data    ), //o
        .o_ecc_enc_data  ( u_lst_dec_o_ecc_enc_data    ), //o
        .o_ecc_ce        ( u_lst_dec_o_ecc_ce          ), //o
        .o_ecc_ue        ( u_lst_dec_o_ecc_ue          )  //o
    );
end
endgenerate

com_spram_shell #(
    .DATA_W   ( TOL_RAM_W ),
    .DEPTH    ( DEPTH     ),
    .STRB_W   ( TOL_RAM_W ),
    .MEM_USER ( MEM_USER  )
)u_com_spram_shell
(
    .clk                 ( clk                 ), //i
    .i_cfg_mem_ctrl      ( i_cfg_mem_ctrl      ), //i
    .i_ce_n              ( u_ram_i_ce_n        ), //i
    .i_we_n              ( u_ram_i_we_n        ), //i
    .i_addr              ( u_ram_i_addr        ), //i
    .i_wr_data           ( u_ram_i_wr_data     ), //i
    .o_rd_data           ( u_ram_o_rd_data     )  //o
);

//assert---------------------------------------------------------------------
`ifdef COM_ASSERT_ON
`COM_PARAM_ASSERT( DATA_W>=4 && DATA_W<=8178, "DATA_W range is [4:8178]" )
`COM_PARAM_ASSERT( DEPTH>=1, "DEPTH must be larger than 0" )
`COM_PARAM_ASSERT( STRB_W>=1 && DATA_W%STRB_W==0, "DATA_W must be divisible by STRB_W" )
`COM_PARAM_ASSERT( ECC_DW>=4 && ECC_DW<=DATA_W, "ECC_DW range is [4:DATA_W]" )
`COM_PARAM_ASSERT( LST_ORI_W==0 || LST_ORI_W>=4, "the last ECC word must be at least 4 bits" )
`COM_PARAM_ASSERT( REQ_PIPE==0 || REQ_PIPE==1, "REQ_PIPE must be 0 or 1" )
`COM_PARAM_ASSERT( RSP_PIPE==0 || RSP_PIPE==1, "RSP_PIPE must be 0 or 1" )
`endif

endmodule //end of com_ecc_spram_shell
""",
    "com_ecc_tpram1ck_shell.sv": r"""/******************************************************************************
*
*  Authors:   wwq,dmg
*    Email:   dmg@sensetime.com
*     Date:   2025/07/07-20:01:49
*
*  Description:
*  - SECDED protected one-clock true dual-port SRAM implementation shell.
*
******************************************************************************/

module com_ecc_tpram1ck_shell #( parameter
    DATA_W   = 32,              //range=[4:8178:]
    DEPTH    = 64,              //range=[1::]
    STRB_W   = 1,               //range=[1:DATA_W:]
    MEM_USER = 0,
    REQ_PIPE = 0,               //range=[0:1:]
    RSP_PIPE = 0,               //range=[0:1:]
    ECC_DW   = DATA_W,          //range=[4:DATA_W:]
    localparam ADDR_W = $clog2(DEPTH)
)
(
input  wire                         clk                 ,
input  wire [`COM_MEM_CTRL_W-1:0]   i_cfg_mem_ctrl      ,
input  wire [`COM_ECC_CTRL_W-1:0]   i_cfg_ecc_ctrl      , //[0]correct_n, [1]inject_en, [3:2]inject_val

input  wire [STRB_W-1:0]            i_wr_en             ,
input  wire [ADDR_W-1:0]            i_wr_addr           ,
input  wire [DATA_W-1:0]            i_wr_data           ,
input  wire                         i_rd_en             ,
input  wire [ADDR_W-1:0]            i_rd_addr           ,
output wire [DATA_W-1:0]            o_rd_data           ,
output wire [1:0]                   o_pls_ecc_err       //,
);
//localparam-----------------------------------------------------------------
localparam NRM_ORI_W     = ECC_DW;
localparam NRM_ECC_W     = F_lut_ecc_width(NRM_ORI_W);
localparam NRM_ECC_NUM   = DATA_W/ECC_DW;
localparam NRM_TOL_W     = NRM_ORI_W*NRM_ECC_NUM;
localparam LST_ORI_W     = DATA_W%ECC_DW;
localparam LST_ECC_W     = LST_ORI_W>0 ? F_lut_ecc_width(LST_ORI_W) : 0;
localparam LST_ECC_NUM   = LST_ORI_W>0;
localparam LST_SAFE_W    = LST_ORI_W>=4 ? LST_ORI_W : 4;
localparam LST_SAFE_ECC_W = F_lut_ecc_width(LST_SAFE_W);
localparam SUB_DW        = DATA_W/STRB_W;
// One RAM row stores one partial-write flag, DATA_W original bits and all SECDED check bits.
// nrm: NRM_ECC_NUM complete ECC words, each with NRM_ORI_W data bits and NRM_ECC_W check bits.
// lst: optional last ECC word with LST_ORI_W data bits and LST_ECC_W check bits.
// Storage order: {partial_write_flag,lst_ecc,nrm_ecc,original_data}.
localparam TOL_RAM_W     = 1+DATA_W+NRM_ECC_W*NRM_ECC_NUM+LST_ECC_W*LST_ECC_NUM;
localparam RD_VLD_DELAY  = 1+REQ_PIPE+RSP_PIPE;

function automatic int F_lut_ecc_width( int ori_bit_width );
    int ret;
    ret = ori_bit_width<=11   ? 5  :
          ori_bit_width<=26   ? 6  :
          ori_bit_width<=57   ? 7  :
          ori_bit_width<=120  ? 8  :
          ori_bit_width<=247  ? 9  :
          ori_bit_width<=502  ? 10 :
          ori_bit_width<=1013 ? 11 :
          ori_bit_width<=2036 ? 12 :
          ori_bit_width<=4083 ? 13 : 14;
    return ret;
endfunction:F_lut_ecc_width

//signal declare-------------------------------------------------------------
reg  [RD_VLD_DELAY-1:0] r_rd_vld_pipe;

wire                   cfg_ecc_correct_n;
wire                   cfg_ecc_inject_en;
wire [1:0]             cfg_ecc_inject_val;
wire                   rd_req;
wire                   wr_req;
wire                   full_write;
wire                   partial_write;
wire                   rd_partial_write_flag;
wire [DATA_W-1:0]      wr_data_inj;
wire [DATA_W-1:0]      stored_rd_data;
wire [DATA_W-1:0]      correct_rd_data;
wire [TOL_RAM_W-1:0]   ecc_ram_wr_data;
wire [TOL_RAM_W-1:0]   ecc_ram_rd_data;
wire [TOL_RAM_W-1:0]   ram_wr_bit_en;
wire                   ecc_ce;
wire                   ecc_ue;

wire [TOL_RAM_W-1:0]   u_ram_i_wr_en;
wire [ADDR_W-1:0]      u_ram_i_wr_addr;
wire [TOL_RAM_W-1:0]   u_ram_i_wr_data;
wire                   u_ram_i_rd_en;
wire [ADDR_W-1:0]      u_ram_i_rd_addr;
wire [TOL_RAM_W-1:0]   u_ram_o_rd_data;

wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0] u_nrm_enc_i_original_data;
wire [NRM_ECC_NUM-1:0][NRM_ECC_W-1:0] u_nrm_enc_i_ecc_dec_data;
wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0] u_nrm_enc_o_correct_data;
wire [NRM_ECC_NUM-1:0][NRM_ECC_W-1:0] u_nrm_enc_o_ecc_enc_data;
wire [NRM_ECC_NUM-1:0]                u_nrm_enc_o_ecc_ce;
wire [NRM_ECC_NUM-1:0]                u_nrm_enc_o_ecc_ue;
wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0] u_nrm_dec_i_original_data;
wire [NRM_ECC_NUM-1:0][NRM_ECC_W-1:0] u_nrm_dec_i_ecc_dec_data;
wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0] u_nrm_dec_o_correct_data;
wire [NRM_ECC_NUM-1:0][NRM_ECC_W-1:0] u_nrm_dec_o_ecc_enc_data;
wire [NRM_ECC_NUM-1:0]                u_nrm_dec_o_ecc_ce;
wire [NRM_ECC_NUM-1:0]                u_nrm_dec_o_ecc_ue;

wire [LST_SAFE_W-1:0]     u_lst_enc_i_original_data;
wire [LST_SAFE_ECC_W-1:0] u_lst_enc_i_ecc_dec_data;
wire [LST_SAFE_W-1:0]     u_lst_enc_o_correct_data;
wire [LST_SAFE_ECC_W-1:0] u_lst_enc_o_ecc_enc_data;
wire                      u_lst_enc_o_ecc_ce;
wire                      u_lst_enc_o_ecc_ue;
wire [LST_SAFE_W-1:0]     u_lst_dec_i_original_data;
wire [LST_SAFE_ECC_W-1:0] u_lst_dec_i_ecc_dec_data;
wire [LST_SAFE_W-1:0]     u_lst_dec_o_correct_data;
wire [LST_SAFE_ECC_W-1:0] u_lst_dec_o_ecc_enc_data;
wire                      u_lst_dec_o_ecc_ce;
wire                      u_lst_dec_o_ecc_ue;

//statement------------------------------------------------------------------
//output assign---
assign o_rd_data = rd_partial_write_flag ? stored_rd_data : correct_rd_data;
assign o_pls_ecc_err = r_rd_vld_pipe[RD_VLD_DELAY-1] ? {ecc_ue,ecc_ce} : '0;

//body---
assign cfg_ecc_correct_n = i_cfg_ecc_ctrl[0];
assign cfg_ecc_inject_en = i_cfg_ecc_ctrl[1];
assign cfg_ecc_inject_val = i_cfg_ecc_ctrl[3:2];
assign rd_req = i_rd_en;
assign wr_req = |i_wr_en;
assign full_write = &i_wr_en;
assign partial_write = wr_req && !full_write;
assign wr_data_inj = cfg_ecc_inject_en ?
                     {i_wr_data[DATA_W-1:2],i_wr_data[1:0]^cfg_ecc_inject_val} :
                     i_wr_data;

assign ecc_ce = !rd_partial_write_flag &&
                ((|u_nrm_dec_o_ecc_ce) || u_lst_dec_o_ecc_ce);
assign ecc_ue = !rd_partial_write_flag &&
                ((|u_nrm_dec_o_ecc_ue) || u_lst_dec_o_ecc_ue);

generate
for( genvar gi=0; gi<STRB_W; gi++ ) begin:gen_ram_wr_bit_en
    assign ram_wr_bit_en[gi*SUB_DW +:SUB_DW] = {SUB_DW{i_wr_en[gi]}};
end
endgenerate
assign ram_wr_bit_en[TOL_RAM_W-2:DATA_W] = {(TOL_RAM_W-DATA_W-1){full_write}};
assign ram_wr_bit_en[TOL_RAM_W-1] = wr_req;

always @(posedge clk) begin
    r_rd_vld_pipe[0] <= rd_req;
    for( int i=1; i<RD_VLD_DELAY; i++ )
        r_rd_vld_pipe[i] <= r_rd_vld_pipe[i-1];
end

//request pipeline
generate
if( REQ_PIPE ) begin:gen_req_pipe
    reg  [TOL_RAM_W-1:0] r_ram_wr_en;
    reg  [ADDR_W-1:0]    r_ram_wr_addr;
    reg  [TOL_RAM_W-1:0] r_ram_wr_data;
    reg                  r_ram_rd_en;
    reg  [ADDR_W-1:0]    r_ram_rd_addr;

    assign u_ram_i_wr_en = r_ram_wr_en;
    assign u_ram_i_wr_addr = r_ram_wr_addr;
    assign u_ram_i_wr_data = r_ram_wr_data;
    assign u_ram_i_rd_en = r_ram_rd_en;
    assign u_ram_i_rd_addr = r_ram_rd_addr;
    always @(posedge clk) begin
        r_ram_wr_en <= ram_wr_bit_en;
        r_ram_wr_addr <= i_wr_addr;
        r_ram_wr_data <= ecc_ram_wr_data;
    end
    always @(posedge clk) begin
        r_ram_rd_en <= i_rd_en;
        r_ram_rd_addr <= i_rd_addr;
    end
end
else begin:gen_req_direct
    assign u_ram_i_wr_en = ram_wr_bit_en;
    assign u_ram_i_wr_addr = i_wr_addr;
    assign u_ram_i_wr_data = ecc_ram_wr_data;
    assign u_ram_i_rd_en = i_rd_en;
    assign u_ram_i_rd_addr = i_rd_addr;
end
endgenerate

//response pipeline
generate
if( RSP_PIPE ) begin:gen_rsp_pipe
    reg [TOL_RAM_W-1:0] r_ram_rd_data;

    assign ecc_ram_rd_data = r_ram_rd_data;
    always @(posedge clk)
        r_ram_rd_data <= u_ram_o_rd_data;
end
else begin:gen_rsp_direct
    assign ecc_ram_rd_data = u_ram_o_rd_data;
end
endgenerate

//ECC data packing
generate
if( LST_ECC_NUM ) begin:gen_lst_pack
    assign ecc_ram_wr_data = {partial_write,u_lst_enc_o_ecc_enc_data,u_nrm_enc_o_ecc_enc_data,wr_data_inj};
    assign {rd_partial_write_flag,u_lst_dec_i_ecc_dec_data,u_nrm_dec_i_ecc_dec_data,stored_rd_data} = ecc_ram_rd_data;
    assign correct_rd_data = {u_lst_dec_o_correct_data,u_nrm_dec_o_correct_data};
end
else begin:gen_nrm_pack
    assign u_lst_dec_i_ecc_dec_data = '0;
    assign u_lst_dec_i_original_data = '0;
    assign u_lst_dec_o_ecc_ce = 1'b0;
    assign u_lst_dec_o_ecc_ue = 1'b0;
    assign ecc_ram_wr_data = {partial_write,u_nrm_enc_o_ecc_enc_data,wr_data_inj};
    assign {rd_partial_write_flag,u_nrm_dec_i_ecc_dec_data,stored_rd_data} = ecc_ram_rd_data;
    assign correct_rd_data = u_nrm_dec_o_correct_data;
end
endgenerate

//instance----
assign u_nrm_enc_i_original_data = i_wr_data[NRM_TOL_W-1:0];
assign u_nrm_enc_i_ecc_dec_data = '0;
com_ecc_secded #(
    .DW ( NRM_ORI_W )
)u_com_ecc_secded_nrm_enc[NRM_ECC_NUM-1:0]
(
    .i_correct_n     ( 1'b1                         ), //i
    .i_original_data ( u_nrm_enc_i_original_data     ), //i
    .i_ecc_dec_data  ( u_nrm_enc_i_ecc_dec_data      ), //i
    .o_correct_data  ( u_nrm_enc_o_correct_data      ), //o
    .o_ecc_enc_data  ( u_nrm_enc_o_ecc_enc_data      ), //o
    .o_ecc_ce        ( u_nrm_enc_o_ecc_ce            ), //o
    .o_ecc_ue        ( u_nrm_enc_o_ecc_ue            )  //o
);

assign u_nrm_dec_i_original_data = stored_rd_data[NRM_TOL_W-1:0];
com_ecc_secded #(
    .DW ( NRM_ORI_W )
)u_com_ecc_secded_nrm_dec[NRM_ECC_NUM-1:0]
(
    .i_correct_n     ( cfg_ecc_correct_n             ), //i
    .i_original_data ( u_nrm_dec_i_original_data     ), //i
    .i_ecc_dec_data  ( u_nrm_dec_i_ecc_dec_data      ), //i
    .o_correct_data  ( u_nrm_dec_o_correct_data      ), //o
    .o_ecc_enc_data  ( u_nrm_dec_o_ecc_enc_data      ), //o
    .o_ecc_ce        ( u_nrm_dec_o_ecc_ce            ), //o
    .o_ecc_ue        ( u_nrm_dec_o_ecc_ue            )  //o
);

generate
if( LST_ECC_NUM ) begin:gen_lst_ecc
    assign u_lst_enc_i_original_data = i_wr_data[NRM_TOL_W +:LST_SAFE_W];
    assign u_lst_enc_i_ecc_dec_data = '0;
    assign u_lst_dec_i_original_data = stored_rd_data[NRM_TOL_W +:LST_SAFE_W];

    com_ecc_secded #(
        .DW ( LST_SAFE_W )
    )u_com_ecc_secded_lst_enc
    (
        .i_correct_n     ( 1'b1                       ), //i
        .i_original_data ( u_lst_enc_i_original_data   ), //i
        .i_ecc_dec_data  ( u_lst_enc_i_ecc_dec_data    ), //i
        .o_correct_data  ( u_lst_enc_o_correct_data    ), //o
        .o_ecc_enc_data  ( u_lst_enc_o_ecc_enc_data    ), //o
        .o_ecc_ce        ( u_lst_enc_o_ecc_ce          ), //o
        .o_ecc_ue        ( u_lst_enc_o_ecc_ue          )  //o
    );

    com_ecc_secded #(
        .DW ( LST_SAFE_W )
    )u_com_ecc_secded_lst_dec
    (
        .i_correct_n     ( cfg_ecc_correct_n           ), //i
        .i_original_data ( u_lst_dec_i_original_data   ), //i
        .i_ecc_dec_data  ( u_lst_dec_i_ecc_dec_data    ), //i
        .o_correct_data  ( u_lst_dec_o_correct_data    ), //o
        .o_ecc_enc_data  ( u_lst_dec_o_ecc_enc_data    ), //o
        .o_ecc_ce        ( u_lst_dec_o_ecc_ce          ), //o
        .o_ecc_ue        ( u_lst_dec_o_ecc_ue          )  //o
    );
end
endgenerate

com_tpram1ck_shell #(
    .DATA_W   ( TOL_RAM_W ),
    .DEPTH    ( DEPTH     ),
    .STRB_W   ( TOL_RAM_W ),
    .MEM_USER ( MEM_USER  )
)u_com_tpram1ck_shell
(
    .clk                 ( clk                 ), //i
    .i_cfg_mem_ctrl      ( i_cfg_mem_ctrl      ), //i
    .i_wr_en             ( u_ram_i_wr_en       ), //i
    .i_wr_addr           ( u_ram_i_wr_addr     ), //i
    .i_wr_data           ( u_ram_i_wr_data     ), //i
    .i_rd_en             ( u_ram_i_rd_en       ), //i
    .i_rd_addr           ( u_ram_i_rd_addr     ), //i
    .o_rd_data           ( u_ram_o_rd_data     )  //o
);

//assert---------------------------------------------------------------------
`ifdef COM_ASSERT_ON
`COM_PARAM_ASSERT( DATA_W>=4 && DATA_W<=8178, "DATA_W range is [4:8178]" )
`COM_PARAM_ASSERT( DEPTH>=1, "DEPTH must be larger than 0" )
`COM_PARAM_ASSERT( STRB_W>=1 && DATA_W%STRB_W==0, "DATA_W must be divisible by STRB_W" )
`COM_PARAM_ASSERT( ECC_DW>=4 && ECC_DW<=DATA_W, "ECC_DW range is [4:DATA_W]" )
`COM_PARAM_ASSERT( LST_ORI_W==0 || LST_ORI_W>=4, "the last ECC word must be at least 4 bits" )
`COM_PARAM_ASSERT( REQ_PIPE==0 || REQ_PIPE==1, "REQ_PIPE must be 0 or 1" )
`COM_PARAM_ASSERT( RSP_PIPE==0 || RSP_PIPE==1, "RSP_PIPE must be 0 or 1" )
`endif

endmodule //end of com_ecc_tpram1ck_shell
""",
    "com_ecc_tpram2ck_shell.sv": r"""/******************************************************************************
*
*  Authors:   wwq,dmg
*    Email:   dmg@sensetime.com
*     Date:   2025/07/07-20:01:49
*
*  Description:
*  - SECDED protected two-clock true dual-port SRAM implementation shell.
*
******************************************************************************/

module com_ecc_tpram2ck_shell #( parameter
    DATA_W   = 32,              //range=[4:8178:]
    DEPTH    = 64,              //range=[1::]
    STRB_W   = 1,               //range=[1:DATA_W:]
    MEM_USER = 0,
    REQ_PIPE = 0,               //range=[0:1:]
    RSP_PIPE = 0,               //range=[0:1:]
    ECC_DW   = DATA_W,          //range=[4:DATA_W:]
    localparam ADDR_W = $clog2(DEPTH)
)
(
input  wire [`COM_MEM_CTRL_W-1:0]   i_cfg_mem_ctrl      ,
input  wire [`COM_ECC_CTRL_W-1:0]   i_cfg_ecc_ctrl      , //[0]correct_n, [1]inject_en, [3:2]inject_val

input  wire                         wr_clk              ,
input  wire [STRB_W-1:0]            i_wr_en             ,
input  wire [ADDR_W-1:0]            i_wr_addr           ,
input  wire [DATA_W-1:0]            i_wr_data           ,
input  wire                         rd_clk              ,
input  wire                         i_rd_en             ,
input  wire [ADDR_W-1:0]            i_rd_addr           ,
output wire [DATA_W-1:0]            o_rd_data           ,
output wire [1:0]                   o_pls_ecc_err       //,
);
//localparam-----------------------------------------------------------------
localparam NRM_ORI_W     = ECC_DW;
localparam NRM_ECC_W     = F_lut_ecc_width(NRM_ORI_W);
localparam NRM_ECC_NUM   = DATA_W/ECC_DW;
localparam NRM_TOL_W     = NRM_ORI_W*NRM_ECC_NUM;
localparam LST_ORI_W     = DATA_W%ECC_DW;
localparam LST_ECC_W     = LST_ORI_W>0 ? F_lut_ecc_width(LST_ORI_W) : 0;
localparam LST_ECC_NUM   = LST_ORI_W>0;
localparam LST_SAFE_W    = LST_ORI_W>=4 ? LST_ORI_W : 4;
localparam LST_SAFE_ECC_W = F_lut_ecc_width(LST_SAFE_W);
localparam SUB_DW        = DATA_W/STRB_W;
// One RAM row stores one partial-write flag, DATA_W original bits and all SECDED check bits.
// nrm: NRM_ECC_NUM complete ECC words, each with NRM_ORI_W data bits and NRM_ECC_W check bits.
// lst: optional last ECC word with LST_ORI_W data bits and LST_ECC_W check bits.
// Storage order: {partial_write_flag,lst_ecc,nrm_ecc,original_data}.
localparam TOL_RAM_W     = 1+DATA_W+NRM_ECC_W*NRM_ECC_NUM+LST_ECC_W*LST_ECC_NUM;
localparam RD_VLD_DELAY  = 1+REQ_PIPE+RSP_PIPE;

function automatic int F_lut_ecc_width( int ori_bit_width );
    int ret;
    ret = ori_bit_width<=11   ? 5  :
          ori_bit_width<=26   ? 6  :
          ori_bit_width<=57   ? 7  :
          ori_bit_width<=120  ? 8  :
          ori_bit_width<=247  ? 9  :
          ori_bit_width<=502  ? 10 :
          ori_bit_width<=1013 ? 11 :
          ori_bit_width<=2036 ? 12 :
          ori_bit_width<=4083 ? 13 : 14;
    return ret;
endfunction:F_lut_ecc_width

//signal declare-------------------------------------------------------------
reg  [RD_VLD_DELAY-1:0] r_rd_vld_pipe;

wire                   cfg_ecc_correct_n;
wire                   cfg_ecc_inject_en;
wire [1:0]             cfg_ecc_inject_val;
wire                   rd_req;
wire                   wr_req;
wire                   full_write;
wire                   partial_write;
wire                   rd_partial_write_flag;
wire [DATA_W-1:0]      wr_data_inj;
wire [DATA_W-1:0]      stored_rd_data;
wire [DATA_W-1:0]      correct_rd_data;
wire [TOL_RAM_W-1:0]   ecc_ram_wr_data;
wire [TOL_RAM_W-1:0]   ecc_ram_rd_data;
wire [TOL_RAM_W-1:0]   ram_wr_bit_en;
wire                   ecc_ce;
wire                   ecc_ue;

wire [TOL_RAM_W-1:0]   u_ram_i_wr_en;
wire [ADDR_W-1:0]      u_ram_i_wr_addr;
wire [TOL_RAM_W-1:0]   u_ram_i_wr_data;
wire                   u_ram_i_rd_en;
wire [ADDR_W-1:0]      u_ram_i_rd_addr;
wire [TOL_RAM_W-1:0]   u_ram_o_rd_data;

wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0] u_nrm_enc_i_original_data;
wire [NRM_ECC_NUM-1:0][NRM_ECC_W-1:0] u_nrm_enc_i_ecc_dec_data;
wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0] u_nrm_enc_o_correct_data;
wire [NRM_ECC_NUM-1:0][NRM_ECC_W-1:0] u_nrm_enc_o_ecc_enc_data;
wire [NRM_ECC_NUM-1:0]                u_nrm_enc_o_ecc_ce;
wire [NRM_ECC_NUM-1:0]                u_nrm_enc_o_ecc_ue;
wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0] u_nrm_dec_i_original_data;
wire [NRM_ECC_NUM-1:0][NRM_ECC_W-1:0] u_nrm_dec_i_ecc_dec_data;
wire [NRM_ECC_NUM-1:0][NRM_ORI_W-1:0] u_nrm_dec_o_correct_data;
wire [NRM_ECC_NUM-1:0][NRM_ECC_W-1:0] u_nrm_dec_o_ecc_enc_data;
wire [NRM_ECC_NUM-1:0]                u_nrm_dec_o_ecc_ce;
wire [NRM_ECC_NUM-1:0]                u_nrm_dec_o_ecc_ue;

wire [LST_SAFE_W-1:0]     u_lst_enc_i_original_data;
wire [LST_SAFE_ECC_W-1:0] u_lst_enc_i_ecc_dec_data;
wire [LST_SAFE_W-1:0]     u_lst_enc_o_correct_data;
wire [LST_SAFE_ECC_W-1:0] u_lst_enc_o_ecc_enc_data;
wire                      u_lst_enc_o_ecc_ce;
wire                      u_lst_enc_o_ecc_ue;
wire [LST_SAFE_W-1:0]     u_lst_dec_i_original_data;
wire [LST_SAFE_ECC_W-1:0] u_lst_dec_i_ecc_dec_data;
wire [LST_SAFE_W-1:0]     u_lst_dec_o_correct_data;
wire [LST_SAFE_ECC_W-1:0] u_lst_dec_o_ecc_enc_data;
wire                      u_lst_dec_o_ecc_ce;
wire                      u_lst_dec_o_ecc_ue;

//statement------------------------------------------------------------------
//output assign---
assign o_rd_data = rd_partial_write_flag ? stored_rd_data : correct_rd_data;
assign o_pls_ecc_err = r_rd_vld_pipe[RD_VLD_DELAY-1] ? {ecc_ue,ecc_ce} : '0;

//body---
assign cfg_ecc_correct_n = i_cfg_ecc_ctrl[0];
assign cfg_ecc_inject_en = i_cfg_ecc_ctrl[1];
assign cfg_ecc_inject_val = i_cfg_ecc_ctrl[3:2];
assign rd_req = i_rd_en;
assign wr_req = |i_wr_en;
assign full_write = &i_wr_en;
assign partial_write = wr_req && !full_write;
assign wr_data_inj = cfg_ecc_inject_en ?
                     {i_wr_data[DATA_W-1:2],i_wr_data[1:0]^cfg_ecc_inject_val} :
                     i_wr_data;

assign ecc_ce = !rd_partial_write_flag &&
                ((|u_nrm_dec_o_ecc_ce) || u_lst_dec_o_ecc_ce);
assign ecc_ue = !rd_partial_write_flag &&
                ((|u_nrm_dec_o_ecc_ue) || u_lst_dec_o_ecc_ue);

generate
for( genvar gi=0; gi<STRB_W; gi++ ) begin:gen_ram_wr_bit_en
    assign ram_wr_bit_en[gi*SUB_DW +:SUB_DW] = {SUB_DW{i_wr_en[gi]}};
end
endgenerate
assign ram_wr_bit_en[TOL_RAM_W-2:DATA_W] = {(TOL_RAM_W-DATA_W-1){full_write}};
assign ram_wr_bit_en[TOL_RAM_W-1] = wr_req;

always @(posedge rd_clk) begin
    r_rd_vld_pipe[0] <= rd_req;
    for( int i=1; i<RD_VLD_DELAY; i++ )
        r_rd_vld_pipe[i] <= r_rd_vld_pipe[i-1];
end

//request pipeline
generate
if( REQ_PIPE ) begin:gen_req_pipe
    reg  [TOL_RAM_W-1:0] r_ram_wr_en;
    reg  [ADDR_W-1:0]    r_ram_wr_addr;
    reg  [TOL_RAM_W-1:0] r_ram_wr_data;
    reg                  r_ram_rd_en;
    reg  [ADDR_W-1:0]    r_ram_rd_addr;

    assign u_ram_i_wr_en = r_ram_wr_en;
    assign u_ram_i_wr_addr = r_ram_wr_addr;
    assign u_ram_i_wr_data = r_ram_wr_data;
    assign u_ram_i_rd_en = r_ram_rd_en;
    assign u_ram_i_rd_addr = r_ram_rd_addr;
    always @(posedge wr_clk) begin
        r_ram_wr_en <= ram_wr_bit_en;
        r_ram_wr_addr <= i_wr_addr;
        r_ram_wr_data <= ecc_ram_wr_data;
    end
    always @(posedge rd_clk) begin
        r_ram_rd_en <= i_rd_en;
        r_ram_rd_addr <= i_rd_addr;
    end
end
else begin:gen_req_direct
    assign u_ram_i_wr_en = ram_wr_bit_en;
    assign u_ram_i_wr_addr = i_wr_addr;
    assign u_ram_i_wr_data = ecc_ram_wr_data;
    assign u_ram_i_rd_en = i_rd_en;
    assign u_ram_i_rd_addr = i_rd_addr;
end
endgenerate

//response pipeline
generate
if( RSP_PIPE ) begin:gen_rsp_pipe
    reg [TOL_RAM_W-1:0] r_ram_rd_data;

    assign ecc_ram_rd_data = r_ram_rd_data;
    always @(posedge rd_clk)
        r_ram_rd_data <= u_ram_o_rd_data;
end
else begin:gen_rsp_direct
    assign ecc_ram_rd_data = u_ram_o_rd_data;
end
endgenerate

//ECC data packing
generate
if( LST_ECC_NUM ) begin:gen_lst_pack
    assign ecc_ram_wr_data = {partial_write,u_lst_enc_o_ecc_enc_data,u_nrm_enc_o_ecc_enc_data,wr_data_inj};
    assign {rd_partial_write_flag,u_lst_dec_i_ecc_dec_data,u_nrm_dec_i_ecc_dec_data,stored_rd_data} = ecc_ram_rd_data;
    assign correct_rd_data = {u_lst_dec_o_correct_data,u_nrm_dec_o_correct_data};
end
else begin:gen_nrm_pack
    assign u_lst_dec_i_ecc_dec_data = '0;
    assign u_lst_dec_i_original_data = '0;
    assign u_lst_dec_o_ecc_ce = 1'b0;
    assign u_lst_dec_o_ecc_ue = 1'b0;
    assign ecc_ram_wr_data = {partial_write,u_nrm_enc_o_ecc_enc_data,wr_data_inj};
    assign {rd_partial_write_flag,u_nrm_dec_i_ecc_dec_data,stored_rd_data} = ecc_ram_rd_data;
    assign correct_rd_data = u_nrm_dec_o_correct_data;
end
endgenerate

//instance----
assign u_nrm_enc_i_original_data = i_wr_data[NRM_TOL_W-1:0];
assign u_nrm_enc_i_ecc_dec_data = '0;
com_ecc_secded #(
    .DW ( NRM_ORI_W )
)u_com_ecc_secded_nrm_enc[NRM_ECC_NUM-1:0]
(
    .i_correct_n     ( 1'b1                         ), //i
    .i_original_data ( u_nrm_enc_i_original_data     ), //i
    .i_ecc_dec_data  ( u_nrm_enc_i_ecc_dec_data      ), //i
    .o_correct_data  ( u_nrm_enc_o_correct_data      ), //o
    .o_ecc_enc_data  ( u_nrm_enc_o_ecc_enc_data      ), //o
    .o_ecc_ce        ( u_nrm_enc_o_ecc_ce            ), //o
    .o_ecc_ue        ( u_nrm_enc_o_ecc_ue            )  //o
);

assign u_nrm_dec_i_original_data = stored_rd_data[NRM_TOL_W-1:0];
com_ecc_secded #(
    .DW ( NRM_ORI_W )
)u_com_ecc_secded_nrm_dec[NRM_ECC_NUM-1:0]
(
    .i_correct_n     ( cfg_ecc_correct_n             ), //i
    .i_original_data ( u_nrm_dec_i_original_data     ), //i
    .i_ecc_dec_data  ( u_nrm_dec_i_ecc_dec_data      ), //i
    .o_correct_data  ( u_nrm_dec_o_correct_data      ), //o
    .o_ecc_enc_data  ( u_nrm_dec_o_ecc_enc_data      ), //o
    .o_ecc_ce        ( u_nrm_dec_o_ecc_ce            ), //o
    .o_ecc_ue        ( u_nrm_dec_o_ecc_ue            )  //o
);

generate
if( LST_ECC_NUM ) begin:gen_lst_ecc
    assign u_lst_enc_i_original_data = i_wr_data[NRM_TOL_W +:LST_SAFE_W];
    assign u_lst_enc_i_ecc_dec_data = '0;
    assign u_lst_dec_i_original_data = stored_rd_data[NRM_TOL_W +:LST_SAFE_W];

    com_ecc_secded #(
        .DW ( LST_SAFE_W )
    )u_com_ecc_secded_lst_enc
    (
        .i_correct_n     ( 1'b1                       ), //i
        .i_original_data ( u_lst_enc_i_original_data   ), //i
        .i_ecc_dec_data  ( u_lst_enc_i_ecc_dec_data    ), //i
        .o_correct_data  ( u_lst_enc_o_correct_data    ), //o
        .o_ecc_enc_data  ( u_lst_enc_o_ecc_enc_data    ), //o
        .o_ecc_ce        ( u_lst_enc_o_ecc_ce          ), //o
        .o_ecc_ue        ( u_lst_enc_o_ecc_ue          )  //o
    );

    com_ecc_secded #(
        .DW ( LST_SAFE_W )
    )u_com_ecc_secded_lst_dec
    (
        .i_correct_n     ( cfg_ecc_correct_n           ), //i
        .i_original_data ( u_lst_dec_i_original_data   ), //i
        .i_ecc_dec_data  ( u_lst_dec_i_ecc_dec_data    ), //i
        .o_correct_data  ( u_lst_dec_o_correct_data    ), //o
        .o_ecc_enc_data  ( u_lst_dec_o_ecc_enc_data    ), //o
        .o_ecc_ce        ( u_lst_dec_o_ecc_ce          ), //o
        .o_ecc_ue        ( u_lst_dec_o_ecc_ue          )  //o
    );
end
endgenerate

com_tpram2ck_shell #(
    .DATA_W   ( TOL_RAM_W ),
    .DEPTH    ( DEPTH     ),
    .STRB_W   ( TOL_RAM_W ),
    .MEM_USER ( MEM_USER  )
)u_com_tpram2ck_shell
(
    .i_cfg_mem_ctrl      ( i_cfg_mem_ctrl      ), //i
    .wr_clk              ( wr_clk              ), //i
    .i_wr_en             ( u_ram_i_wr_en       ), //i
    .i_wr_addr           ( u_ram_i_wr_addr     ), //i
    .i_wr_data           ( u_ram_i_wr_data     ), //i
    .rd_clk              ( rd_clk              ), //i
    .i_rd_en             ( u_ram_i_rd_en       ), //i
    .i_rd_addr           ( u_ram_i_rd_addr     ), //i
    .o_rd_data           ( u_ram_o_rd_data     )  //o
);

//assert---------------------------------------------------------------------
`ifdef COM_ASSERT_ON
`COM_PARAM_ASSERT( DATA_W>=4 && DATA_W<=8178, "DATA_W range is [4:8178]" )
`COM_PARAM_ASSERT( DEPTH>=1, "DEPTH must be larger than 0" )
`COM_PARAM_ASSERT( STRB_W>=1 && DATA_W%STRB_W==0, "DATA_W must be divisible by STRB_W" )
`COM_PARAM_ASSERT( ECC_DW>=4 && ECC_DW<=DATA_W, "ECC_DW range is [4:DATA_W]" )
`COM_PARAM_ASSERT( LST_ORI_W==0 || LST_ORI_W>=4, "the last ECC word must be at least 4 bits" )
`COM_PARAM_ASSERT( REQ_PIPE==0 || REQ_PIPE==1, "REQ_PIPE must be 0 or 1" )
`COM_PARAM_ASSERT( RSP_PIPE==0 || RSP_PIPE==1, "RSP_PIPE must be 0 or 1" )
`endif

endmodule //end of com_ecc_tpram2ck_shell
""",
    "com_spram_shell.sv": r"""/******************************************************************************
*
*  Authors:   wwq,dmg
*    Email:   dmg@sensetime.com
*     Date:   2025/07/07-20:01:49
*
*  Description:
*  - Single-port SRAM implementation shell.
*
******************************************************************************/

module com_spram_shell #( parameter
    DATA_W   = 32, //range=[1::]
    DEPTH    = 64, //range=[1::]
    STRB_W   = 1,  //range=[1:DATA_W:]
    MEM_USER = 0,
    localparam ADDR_W = $clog2(DEPTH)
)
(
input  wire                         clk                 ,
input  wire [`COM_MEM_CTRL_W-1:0]   i_cfg_mem_ctrl      ,

input  wire                         i_ce_n              ,
input  wire [STRB_W-1:0]            i_we_n              , //0: write, 1: read
input  wire [ADDR_W-1:0]            i_addr              ,
input  wire [DATA_W-1:0]            i_wr_data           ,
output wire [DATA_W-1:0]            o_rd_data           //,
);
//localparam-----------------------------------------------------------------
`ifdef COM_RAM_AS_REG
localparam RAM_AS_REG = 1;
`else
localparam RAM_AS_REG = 0;
`endif
localparam MEM_USE_CELL = DEPTH>=30 && DATA_W*DEPTH>=1024;

//signal declare-------------------------------------------------------------
wire [STRB_W-1:0]      u_ram_i_wr_en;
wire [ADDR_W-1:0]      u_ram_i_wr_addr;
wire [DATA_W-1:0]      u_ram_i_wr_data;
wire                   u_ram_i_rd_en;
wire [ADDR_W-1:0]      u_ram_i_rd_addr;
wire [DATA_W-1:0]      u_ram_o_rd_data;
wire                   use_cell;

//statement------------------------------------------------------------------
`ifndef COM_RAM_AS_BBOX
//output assign---
assign o_rd_data = u_ram_o_rd_data;

//body---
assign u_ram_i_wr_en = {STRB_W{!i_ce_n}} & ~i_we_n;
assign u_ram_i_wr_addr = i_addr;
assign u_ram_i_wr_data = i_wr_data;
assign u_ram_i_rd_en = !i_ce_n && (&i_we_n);
assign u_ram_i_rd_addr = i_addr;

generate
if( RAM_AS_REG || !MEM_USE_CELL ) begin:gen_ram_as_reg
    com_tpram_reg #(
        .DATA_W              ( DATA_W             ),
        .DEPTH               ( DEPTH              ),
        .STRB_W              ( STRB_W             )
    )u_com_tpram_reg
    (
        .wr_clk              ( clk                ), //i
        .wr_en               ( u_ram_i_wr_en      ), //i
        .wr_addr             ( u_ram_i_wr_addr    ), //i
        .wr_data             ( u_ram_i_wr_data    ), //i
        .rd_clk              ( clk                ), //i
        .rd_en               ( u_ram_i_rd_en      ), //i
        .rd_addr             ( u_ram_i_rd_addr    ), //i
        .rd_data             ( u_ram_o_rd_data    )  //o
    );
    assign use_cell = 1'b0;
end
else begin:gen_ram_as_cell
// Start of user logic.
    if( 0 ) begin:gen_none
        assign use_cell = 1'b1;
    end
// End of user logic.
    else begin:gen_ram_not_found
        // Enable strict checking to reject any shape without a SRAM PHY.
        `ifdef COM_RAM_NFOUND_CHK
        com_spram_not_found
        `else
        com_tpram_reg
        `endif
        #(
            .DATA_W          ( DATA_W             ),
            .DEPTH           ( DEPTH              ),
            .STRB_W          ( STRB_W             )
        )u_com_tpram_reg
        (
            .wr_clk          ( clk                ), //i
            .wr_en           ( u_ram_i_wr_en      ), //i
            .wr_addr         ( u_ram_i_wr_addr    ), //i
            .wr_data         ( u_ram_i_wr_data    ), //i
            .rd_clk          ( clk                ), //i
            .rd_en           ( u_ram_i_rd_en      ), //i
            .rd_addr         ( u_ram_i_rd_addr    ), //i
            .rd_data         ( u_ram_o_rd_data    )  //o
        );
        assign use_cell = 1'b0;
    end
end
endgenerate
`endif

//report---------------------------------------------------------------------
// synopsys translate_off
`ifndef COM_REPORT_OFF
integer fp_mem;
string s;
string str_size;
string str_user;
string str_mem_type;
initial begin
    str_mem_type = "spram";
    fp_mem = $fopen({"./",str_mem_type,".lst"},"wt");
    $fclose(fp_mem);
end
initial begin
    #1;
    fp_mem = $fopen({"./",str_mem_type,".lst"},"at");
    str_user = "";
    if( MEM_USER!=0 )
        str_user = $psprintf("_usr%1d",MEM_USER);
    str_size = STRB_W==1 ? $psprintf("%1dx%1d",DEPTH,DATA_W) :
                           $psprintf("%1dx%1dx%1d",DEPTH,DATA_W,STRB_W);
    s = {str_mem_type,str_size,str_user};

    if( use_cell )
        $fwrite(fp_mem,"%-20s    Info: normal ram as cell;  %m\n",s);
    else if( !MEM_USE_CELL )
        $fwrite(fp_mem,"%-20s Message: small memory as dff; %m\n",s);
    else
        $fwrite(fp_mem,"%-20s Warning: can't find wrapper;  %m\n",s);
end
`endif
// synopsys translate_on
//assert---------------------------------------------------------------------
`ifdef COM_ASSERT_ON
`COM_PARAM_ASSERT( DEPTH>=1, "DEPTH must be larger than 0" )
`COM_PARAM_ASSERT( STRB_W>=1 && DATA_W%STRB_W==0, "DATA_W must be divisible by STRB_W" )
`endif

endmodule //end of com_spram_shell
""",
    "com_sprom_manual.sv": r"""/******************************************************************************
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
""",
    "com_sprom_shell.sv": r"""/******************************************************************************
*
*  Authors:   moc,dmg
*    Email:   dmg@sensetime.com
*     Date:   2025/07/07-20:01:49
*
*  Description:
*  - Single-port ROM implementation shell.
*
******************************************************************************/

module com_sprom_shell #( parameter
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
//localparam-----------------------------------------------------------------
`ifdef COM_RAM_AS_REG
localparam RAM_AS_REG = 1;
`else
localparam RAM_AS_REG = 0;
`endif

//signal declare-------------------------------------------------------------
wire                   u_rom_i_rd_en;
wire [ADDR_W-1:0]      u_rom_i_rd_addr;
wire [DATA_W-1:0]      u_rom_o_rd_data;
wire                   use_cell;

//statement------------------------------------------------------------------
`ifndef COM_RAM_AS_BBOX
//output assign---
assign o_rd_data = u_rom_o_rd_data;

//body---
assign u_rom_i_rd_en = i_rd_en;
assign u_rom_i_rd_addr = i_rd_addr;

generate
if( RAM_AS_REG ) begin:gen_rom_as_reg
    assign u_rom_o_rd_data = '0;
    assign use_cell = 1'b0;
end
else begin:gen_rom_as_cell
// Start of user logic.
    if( 0 ) begin:gen_none
        assign use_cell = 1'b1;
    end
// End of user logic.
    else begin:gen_rom_not_found
        // Enable strict checking to reject any shape without a ROM PHY.
        `ifdef COM_RAM_NFOUND_CHK
        com_sprom_not_found u_com_sprom_not_found();
        `endif
        assign u_rom_o_rd_data = '0;
        assign use_cell = 1'b0;
    end
end
endgenerate

//report---------------------------------------------------------------------
// synopsys translate_off
`ifndef COM_REPORT_OFF
integer fp_mem;
string s;
string str_size;
string str_user;
string str_mem_type;
initial begin
    str_mem_type = "sprom";
    fp_mem = $fopen({"./",str_mem_type,".lst"},"wt");
    $fclose(fp_mem);
end
initial begin
    #1;
    fp_mem = $fopen({"./",str_mem_type,".lst"},"at");
    str_user = "";
    if( MEM_USER!=0 )
        str_user = $psprintf("_usr%1d",MEM_USER);
    str_size = $psprintf("%1dx%1d",DEPTH,DATA_W);
    s = {str_mem_type,str_size,str_user};

    if( use_cell )
        $fwrite(fp_mem,"%-20s    Info: normal ram as cell;  %m\n",s);
    else
        $fwrite(fp_mem,"%-20s Warning: can't find wrapper;  %m\n",s);
end
`endif
// synopsys translate_on
//assert---------------------------------------------------------------------
`ifdef COM_ASSERT_ON
`COM_PARAM_ASSERT( DEPTH>=1, "DEPTH must be larger than 0" )
`endif

endmodule //end of com_sprom_shell
""",
    "com_tpram1ck_shell.sv": r"""/******************************************************************************
*
*  Authors:   wwq,dmg
*    Email:   dmg@sensetime.com
*     Date:   2025/07/07-20:01:49
*
*  Description:
*  - One-clock true dual-port SRAM implementation shell.
*
******************************************************************************/

module com_tpram1ck_shell #( parameter
    DATA_W   = 32, //range=[1::]
    DEPTH    = 64, //range=[1::]
    STRB_W   = 1,  //range=[1:DATA_W:]
    MEM_USER = 0,
    localparam ADDR_W = $clog2(DEPTH)
)
(
input  wire                         clk                 ,
input  wire [`COM_MEM_CTRL_W-1:0]   i_cfg_mem_ctrl      ,

input  wire [STRB_W-1:0]            i_wr_en             ,
input  wire [ADDR_W-1:0]            i_wr_addr           ,
input  wire [DATA_W-1:0]            i_wr_data           ,
input  wire                         i_rd_en             ,
input  wire [ADDR_W-1:0]            i_rd_addr           ,
output wire [DATA_W-1:0]            o_rd_data           //,
);
//localparam-----------------------------------------------------------------
`ifdef COM_RAM_AS_REG
localparam RAM_AS_REG = 1;
`else
localparam RAM_AS_REG = 0;
`endif
localparam MEM_USE_CELL = DEPTH>=30 && DATA_W*DEPTH>=1024;

//signal declare-------------------------------------------------------------
wire [STRB_W-1:0]      u_ram_i_wr_en;
wire [ADDR_W-1:0]      u_ram_i_wr_addr;
wire [DATA_W-1:0]      u_ram_i_wr_data;
wire                   u_ram_i_rd_en;
wire [ADDR_W-1:0]      u_ram_i_rd_addr;
wire [DATA_W-1:0]      u_ram_o_rd_data;
wire                   use_cell;

//statement------------------------------------------------------------------
`ifndef COM_RAM_AS_BBOX
//output assign---
assign o_rd_data = u_ram_o_rd_data;

//body---
assign u_ram_i_wr_en = i_wr_en;
assign u_ram_i_wr_addr = i_wr_addr;
assign u_ram_i_wr_data = i_wr_data;
assign u_ram_i_rd_en = i_rd_en;
assign u_ram_i_rd_addr = i_rd_addr;

generate
if( RAM_AS_REG || !MEM_USE_CELL ) begin:gen_ram_as_reg
    com_tpram_reg #(
        .DATA_W              ( DATA_W             ),
        .DEPTH               ( DEPTH              ),
        .STRB_W              ( STRB_W             )
    )u_com_tpram_reg
    (
        .wr_clk              ( clk                ), //i
        .wr_en               ( u_ram_i_wr_en      ), //i
        .wr_addr             ( u_ram_i_wr_addr    ), //i
        .wr_data             ( u_ram_i_wr_data    ), //i
        .rd_clk              ( clk                ), //i
        .rd_en               ( u_ram_i_rd_en      ), //i
        .rd_addr             ( u_ram_i_rd_addr    ), //i
        .rd_data             ( u_ram_o_rd_data    )  //o
    );
    assign use_cell = 1'b0;
end
else begin:gen_ram_as_cell
// Start of user logic.
    if( 0 ) begin:gen_none
        assign use_cell = 1'b1;
    end
// End of user logic.
    else begin:gen_ram_not_found
        // Enable strict checking to reject any shape without a SRAM PHY.
        `ifdef COM_RAM_NFOUND_CHK
        com_tpram1ck_not_found
        `else
        com_tpram_reg
        `endif
        #(
            .DATA_W          ( DATA_W             ),
            .DEPTH           ( DEPTH              ),
            .STRB_W          ( STRB_W             )
        )u_com_tpram_reg
        (
            .wr_clk          ( clk                ), //i
            .wr_en           ( u_ram_i_wr_en      ), //i
            .wr_addr         ( u_ram_i_wr_addr    ), //i
            .wr_data         ( u_ram_i_wr_data    ), //i
            .rd_clk          ( clk                ), //i
            .rd_en           ( u_ram_i_rd_en      ), //i
            .rd_addr         ( u_ram_i_rd_addr    ), //i
            .rd_data         ( u_ram_o_rd_data    )  //o
        );
        assign use_cell = 1'b0;
    end
end
endgenerate
`endif

//report---------------------------------------------------------------------
// synopsys translate_off
`ifndef COM_REPORT_OFF
integer fp_mem;
string s;
string str_size;
string str_user;
string str_mem_type;
initial begin
    str_mem_type = "tpram1ck";
    fp_mem = $fopen({"./",str_mem_type,".lst"},"wt");
    $fclose(fp_mem);
end
initial begin
    #1;
    fp_mem = $fopen({"./",str_mem_type,".lst"},"at");
    str_user = "";
    if( MEM_USER!=0 )
        str_user = $psprintf("_usr%1d",MEM_USER);
    str_size = STRB_W==1 ? $psprintf("%1dx%1d",DEPTH,DATA_W) :
                           $psprintf("%1dx%1dx%1d",DEPTH,DATA_W,STRB_W);
    s = {str_mem_type,str_size,str_user};

    if( use_cell )
        $fwrite(fp_mem,"%-20s    Info: normal ram as cell;  %m\n",s);
    else if( !MEM_USE_CELL )
        $fwrite(fp_mem,"%-20s Message: small memory as dff; %m\n",s);
    else
        $fwrite(fp_mem,"%-20s Warning: can't find wrapper;  %m\n",s);
end
`endif
// synopsys translate_on
//assert---------------------------------------------------------------------
`ifdef COM_ASSERT_ON
`COM_PARAM_ASSERT( DEPTH>=1, "DEPTH must be larger than 0" )
`COM_PARAM_ASSERT( STRB_W>=1 && DATA_W%STRB_W==0, "DATA_W must be divisible by STRB_W" )
`endif

endmodule //end of com_tpram1ck_shell
""",
    "com_tpram2ck_shell.sv": r"""/******************************************************************************
*
*  Authors:   wwq,dmg
*    Email:   dmg@sensetime.com
*     Date:   2025/07/07-20:01:49
*
*  Description:
*  - Two-clock true dual-port SRAM implementation shell.
*
******************************************************************************/

module com_tpram2ck_shell #( parameter
    DATA_W   = 32, //range=[1::]
    DEPTH    = 64, //range=[1::]
    STRB_W   = 1,  //range=[1:DATA_W:]
    MEM_USER = 0,
    localparam ADDR_W = $clog2(DEPTH)
)
(
input  wire [`COM_MEM_CTRL_W-1:0]   i_cfg_mem_ctrl      ,

input  wire                         wr_clk              ,
input  wire [STRB_W-1:0]            i_wr_en             ,
input  wire [ADDR_W-1:0]            i_wr_addr           ,
input  wire [DATA_W-1:0]            i_wr_data           ,
input  wire                         rd_clk              ,
input  wire                         i_rd_en             ,
input  wire [ADDR_W-1:0]            i_rd_addr           ,
output wire [DATA_W-1:0]            o_rd_data           //,
);
//localparam-----------------------------------------------------------------
`ifdef COM_RAM_AS_REG
localparam RAM_AS_REG = 1;
`else
localparam RAM_AS_REG = 0;
`endif
localparam MEM_USE_CELL = DEPTH>=30 && DATA_W*DEPTH>=1024;

//signal declare-------------------------------------------------------------
wire [STRB_W-1:0]      u_ram_i_wr_en;
wire [ADDR_W-1:0]      u_ram_i_wr_addr;
wire [DATA_W-1:0]      u_ram_i_wr_data;
wire                   u_ram_i_rd_en;
wire [ADDR_W-1:0]      u_ram_i_rd_addr;
wire [DATA_W-1:0]      u_ram_o_rd_data;
wire                   use_cell;

//statement------------------------------------------------------------------
`ifndef COM_RAM_AS_BBOX
//output assign---
assign o_rd_data = u_ram_o_rd_data;

//body---
assign u_ram_i_wr_en = i_wr_en;
assign u_ram_i_wr_addr = i_wr_addr;
assign u_ram_i_wr_data = i_wr_data;
assign u_ram_i_rd_en = i_rd_en;
assign u_ram_i_rd_addr = i_rd_addr;

generate
if( RAM_AS_REG || !MEM_USE_CELL ) begin:gen_ram_as_reg
    com_tpram_reg #(
        .DATA_W              ( DATA_W             ),
        .DEPTH               ( DEPTH              ),
        .STRB_W              ( STRB_W             )
    )u_com_tpram_reg
    (
        .wr_clk              ( wr_clk             ), //i
        .wr_en               ( u_ram_i_wr_en      ), //i
        .wr_addr             ( u_ram_i_wr_addr    ), //i
        .wr_data             ( u_ram_i_wr_data    ), //i
        .rd_clk              ( rd_clk             ), //i
        .rd_en               ( u_ram_i_rd_en      ), //i
        .rd_addr             ( u_ram_i_rd_addr    ), //i
        .rd_data             ( u_ram_o_rd_data    )  //o
    );
    assign use_cell = 1'b0;
end
else begin:gen_ram_as_cell
// Start of user logic.
    if( 0 ) begin:gen_none
        assign use_cell = 1'b1;
    end
// End of user logic.
    else begin:gen_ram_not_found
        // Enable strict checking to reject any shape without a SRAM PHY.
        `ifdef COM_RAM_NFOUND_CHK
        com_tpram2ck_not_found
        `else
        com_tpram_reg
        `endif
        #(
            .DATA_W          ( DATA_W             ),
            .DEPTH           ( DEPTH              ),
            .STRB_W          ( STRB_W             )
        )u_com_tpram_reg
        (
            .wr_clk          ( wr_clk             ), //i
            .wr_en           ( u_ram_i_wr_en      ), //i
            .wr_addr         ( u_ram_i_wr_addr    ), //i
            .wr_data         ( u_ram_i_wr_data    ), //i
            .rd_clk          ( rd_clk             ), //i
            .rd_en           ( u_ram_i_rd_en      ), //i
            .rd_addr         ( u_ram_i_rd_addr    ), //i
            .rd_data         ( u_ram_o_rd_data    )  //o
        );
        assign use_cell = 1'b0;
    end
end
endgenerate

//report---------------------------------------------------------------------
// synopsys translate_off
`ifndef COM_REPORT_OFF
integer fp_mem;
string s;
string str_size;
string str_user;
string str_mem_type;
initial begin
    str_mem_type = "tpram2ck";
    fp_mem = $fopen({"./",str_mem_type,".lst"},"wt");
    $fclose(fp_mem);
end
initial begin
    #1;
    fp_mem = $fopen({"./",str_mem_type,".lst"},"at");
    str_user = "";
    if( MEM_USER!=0 )
        str_user = $psprintf("_usr%1d",MEM_USER);
    str_size = STRB_W==1 ? $psprintf("%1dx%1d",DEPTH,DATA_W) :
                           $psprintf("%1dx%1dx%1d",DEPTH,DATA_W,STRB_W);
    s = {str_mem_type,str_size,str_user};

    if( use_cell )
        $fwrite(fp_mem,"%-20s    Info: normal ram as cell;  %m\n",s);
    else if( !MEM_USE_CELL )
        $fwrite(fp_mem,"%-20s Message: small memory as dff; %m\n",s);
    else
        $fwrite(fp_mem,"%-20s Warning: can't find wrapper;  %m\n",s);
end
`endif
// synopsys translate_on
//assert---------------------------------------------------------------------
`ifdef COM_ASSERT_ON
`COM_PARAM_ASSERT( DEPTH>=1, "DEPTH must be larger than 0" )
`COM_PARAM_ASSERT( STRB_W>=1 && DATA_W%STRB_W==0, "DATA_W must be divisible by STRB_W" )
`endif

endmodule //end of com_tpram2ck_shell
""",
}
