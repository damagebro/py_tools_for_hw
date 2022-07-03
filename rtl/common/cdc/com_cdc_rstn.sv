//////////////////////////////////////////////////////////////////////////////
//
//  Description: Clock Domain Cross for Resetn.
//
//  Authors:   wwq
//  Version:   1.0
//
//////////////////////////////////////////////////////////////////////////////

`ifndef com_cdc_rstn_v
`define com_cdc_rstn_v

module com_cdc_rstn(
    input   irst_n,
    input   sclk,
    output  srst_n
    );

    com_cdc_sig#(
        .DATA_W (1      )
        )sinst(
        .oclk   (sclk   ),
        .orst_n (irst_n ),
        .idata  (1'b1   ),
        .odata  (srst_n )
        );

endmodule

`endif
