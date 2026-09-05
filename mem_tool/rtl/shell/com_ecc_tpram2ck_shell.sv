/******************************************************************************
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
