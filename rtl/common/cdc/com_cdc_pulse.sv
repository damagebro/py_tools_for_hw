//////////////////////////////////////////////////////////////////////////////
//
//  Description: Clock Domain Cross for Pulse.
//
//  Authors:   wwq
//  Version:   1.0
//
//   src_pulse->src_level->dst_level->src_ack_level, cdc pulse handshake;
//////////////////////////////////////////////////////////////////////////////

`ifndef com_cdc_pulse_v
`define com_cdc_pulse_v

module com_cdc_pulse
(
input   wire   iclk    ,
input   wire   irst_n  ,
input   wire   ipulse  ,

input   wire   oclk    ,
input   wire   orst_n  ,
output  wire   opulse  //,
);

wire ipulse_use;
reg  rc_src_level;
wire src_level = rc_src_level;
wire dst_level;
wire src_ack_level;
wire src_ack_pulse;

com_edge_detect #( .MODE("posedge") ) zr_com_edge_detect_ipulse(
    .clk        ( iclk         ), //i
    .rst_n      ( irst_n       ), //i
    .level_in   ( ipulse       ), //i
    .pulse_out  ( ipulse_use   )  //o
);

always @(posedge iclk or negedge irst_n)
begin
    if( !irst_n )
        rc_src_level <= 1'b0;
    else if( ipulse )
        rc_src_level <= 1'b1;
    else if( src_ack_pulse )
        rc_src_level <= 1'b0;
end

com_cdc_sig#(
    .DATA_W (1      )
)zr_com_cdc_sig_s2d(
    .oclk   (oclk         ), //i
    .orst_n (orst_n       ), //i
    .idata  (src_level    ), //i
    .odata  (dst_level    )  //o
);
com_edge_detect #( .MODE("posedge") ) zr_com_edge_detect_dst_pulse(
    .clk        ( oclk         ), //i
    .rst_n      ( orst_n       ), //i
    .level_in   ( dst_level    ), //i
    .pulse_out  ( opulse       )  //o
);

com_cdc_sig#(
    .DATA_W (1      )
)zr_com_cdc_sig_d2s(
    .oclk   (iclk         ), //i
    .orst_n (irst_n       ), //i
    .idata  (dst_level    ), //i
    .odata  (src_ack_level)  //o
);
com_edge_detect #( .MODE("posedge") ) zr_com_edge_detect_ack_pulse(
    .clk        ( iclk         ), //i
    .rst_n      ( irst_n       ), //i
    .level_in   ( src_ack_level), //i
    .pulse_out  ( src_ack_pulse)  //o
);

//------------------------------------------------------------------------------
// Report & Assertion.
//------------------------------------------------------------------------------

endmodule

`endif