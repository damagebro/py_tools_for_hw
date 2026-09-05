//////////////////////////////////////////////////////////////////////////////
//
//  Description: Combinational SECDED encoder and decoder.
//
//////////////////////////////////////////////////////////////////////////////

module com_ecc_secded #(
    parameter  DW = 32, //range=[4:8178]
    localparam ECC_W = DW<=11   ? 5  :
                       DW<=26   ? 6  :
                       DW<=57   ? 7  :
                       DW<=120  ? 8  :
                       DW<=247  ? 9  :
                       DW<=502  ? 10 :
                       DW<=1013 ? 11 :
                       DW<=2036 ? 12 :
                       DW<=4083 ? 13 : 14
)
(
input  wire                 i_correct_n       , //0: correct single-bit error
input  wire [DW-1:0]        i_original_data   ,
input  wire [ECC_W-1:0]     i_ecc_dec_data    ,
output wire [DW-1:0]        o_correct_data    ,
output wire [ECC_W-1:0]     o_ecc_enc_data    ,
output wire                 o_ecc_ce          ,
output wire                 o_ecc_ue          //,
);
//localparam-----------------------------------------------------------------
localparam HAMMING_W = ECC_W-1;
localparam CODE_W    = DW+HAMMING_W;
`ifdef COM_ASSERT_ON
`COM_PARAM_ASSERT((DW>=4 && DW<=8178), "ecc data width range=[4:8178]")
`endif

//signal declare-------------------------------------------------------------
`ifdef COM_ECC_USE_RTL
reg  [HAMMING_W-1:0] w_enc_hamming;
reg                  w_enc_overall;
reg  [HAMMING_W-1:0] w_dec_syndrome;
reg                  w_dec_overall_err;
reg  [DW-1:0]        w_correct_data;
reg                  w_ecc_ce;
reg                  w_ecc_ue;

integer code_pos;
integer data_idx;
integer parity_idx;
integer error_pos;
`else
wire                 u_ecc_enc_i_gen;
wire                 u_ecc_enc_i_correct_n;
wire [DW-1:0]        u_ecc_enc_i_datain;
wire [ECC_W-1:0]     u_ecc_enc_i_chkin;
wire [ECC_W-1:0]     u_ecc_enc_o_chkout;

wire                 u_ecc_dec_i_gen;
wire                 u_ecc_dec_i_correct_n;
wire [DW-1:0]        u_ecc_dec_i_datain;
wire [ECC_W-1:0]     u_ecc_dec_i_chkin;
wire                 u_ecc_dec_o_err_detect;
wire                 u_ecc_dec_o_err_multpl;
wire [DW-1:0]        u_ecc_dec_o_dataout;
`endif

//output assign--------------------------------------------------------------
`ifdef COM_ECC_USE_RTL
assign o_correct_data = !i_correct_n ? w_correct_data : i_original_data;
assign o_ecc_enc_data = {w_enc_overall,w_enc_hamming};
assign o_ecc_ce       = w_ecc_ce;
assign o_ecc_ue       = w_ecc_ue;
`else
assign o_correct_data = u_ecc_dec_o_dataout;
assign o_ecc_enc_data = u_ecc_enc_o_chkout;
assign o_ecc_ce       = u_ecc_dec_o_err_detect && !u_ecc_dec_o_err_multpl;
assign o_ecc_ue       = u_ecc_dec_o_err_multpl;
`endif

//statement------------------------------------------------------------------
`ifdef COM_ECC_USE_RTL
always@* begin
    w_enc_hamming = '0;
    data_idx = 0;
    for( code_pos=1; code_pos<=CODE_W; code_pos=code_pos+1 ) begin
        if( (code_pos & (code_pos-1))!=0 ) begin
            for( parity_idx=0; parity_idx<HAMMING_W; parity_idx=parity_idx+1 ) begin
                if( (code_pos & (1<<parity_idx))!=0 )
                    w_enc_hamming[parity_idx] = w_enc_hamming[parity_idx] ^ i_original_data[data_idx];
            end
            data_idx = data_idx+1;
        end
    end
    w_enc_overall = ^{i_original_data,w_enc_hamming};

    w_dec_syndrome = i_ecc_dec_data[HAMMING_W-1:0];
    data_idx = 0;
    for( code_pos=1; code_pos<=CODE_W; code_pos=code_pos+1 ) begin
        if( (code_pos & (code_pos-1))!=0 ) begin
            for( parity_idx=0; parity_idx<HAMMING_W; parity_idx=parity_idx+1 ) begin
                if( (code_pos & (1<<parity_idx))!=0 )
                    w_dec_syndrome[parity_idx] = w_dec_syndrome[parity_idx] ^ i_original_data[data_idx];
            end
            data_idx = data_idx+1;
        end
    end

    w_dec_overall_err = ^{i_original_data,i_ecc_dec_data};
    w_correct_data = i_original_data;
    w_ecc_ce = 1'b0;
    w_ecc_ue = 1'b0;
    error_pos = w_dec_syndrome;
    if( w_dec_overall_err ) begin
        w_ecc_ce = 1'b1;
        if( |w_dec_syndrome ) begin
            data_idx = 0;
            for( code_pos=1; code_pos<=CODE_W; code_pos=code_pos+1 ) begin
                if( (code_pos & (code_pos-1))!=0 ) begin
                    if( code_pos==error_pos )
                        w_correct_data[data_idx] = !w_correct_data[data_idx];
                    data_idx = data_idx+1;
                end
            end
        end
    end
    else if( |w_dec_syndrome ) begin
        w_ecc_ue = 1'b1;
    end
end
`else
assign u_ecc_enc_i_gen       = 1'b1;
assign u_ecc_enc_i_correct_n = 1'b1;
assign u_ecc_enc_i_datain    = i_original_data;
assign u_ecc_enc_i_chkin     = '0;

assign u_ecc_dec_i_gen       = 1'b0;
assign u_ecc_dec_i_correct_n = i_correct_n;
assign u_ecc_dec_i_datain    = i_original_data;
assign u_ecc_dec_i_chkin     = i_ecc_dec_data;

DW_ecc #(
    .width    ( DW    ),
    .chkbits  ( ECC_W ),
    .synd_sel ( 0     )
)u_ecc_enc
(
    .gen        ( u_ecc_enc_i_gen       ), //i
    .correct_n  ( u_ecc_enc_i_correct_n ), //i
    .datain     ( u_ecc_enc_i_datain    ), //i
    .chkin      ( u_ecc_enc_i_chkin     ), //i
    .err_detect (                       ), //o
    .err_multpl (                       ), //o
    .dataout    (                       ), //o
    .chkout     ( u_ecc_enc_o_chkout    )  //o
);

DW_ecc #(
    .width    ( DW    ),
    .chkbits  ( ECC_W ),
    .synd_sel ( 1     )
)u_ecc_dec
(
    .gen        ( u_ecc_dec_i_gen          ), //i
    .correct_n  ( u_ecc_dec_i_correct_n    ), //i
    .datain     ( u_ecc_dec_i_datain       ), //i
    .chkin      ( u_ecc_dec_i_chkin        ), //i
    .err_detect ( u_ecc_dec_o_err_detect   ), //o
    .err_multpl ( u_ecc_dec_o_err_multpl   ), //o
    .dataout    ( u_ecc_dec_o_dataout      ), //o
    .chkout     (                          )  //o
);
`endif

endmodule
