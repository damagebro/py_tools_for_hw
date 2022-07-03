//////////////////////////////////////////////////////////////////////////////
//
//  Description: Clock Domain Cross for multi-bit data.
//
//  Authors:   wwq
//  Version:   2.0
//////////////////////////////////////////////////////////////////////////////
module com_cdc_sig#(
    parameter DATA_W
    )(
    input               oclk,
    input               orst_n,
    input  [DATA_W-1:0] idata,
    output [DATA_W-1:0] odata
    );

    localparam SYNC_S = `COM_SYNC_STAGE;

`ifdef COM_FPGA
    (*ASYNC_REG = "TRUE"*) reg  [SYNC_S-1:0][DATA_W-1:0] sdata;

    always@(posedge oclk or negedge orst_n)
    if(!orst_n) begin
        sdata <= '0;
    end
    else begin
        sdata <= {sdata[SYNC_S-2:0], idata};
    end
    assign odata = sdata[SYNC_S-1];

`else
    `ifdef COM_CDC_AS_REG
        (*ASYNC_REG = "TRUE"*) logic [SYNC_S-1:0][DATA_W-1:0] sdata;

        always@(posedge oclk or negedge orst_n)
        if(!orst_n) begin
            sdata <= '0;
        end
        else begin
            sdata <= {sdata[SYNC_S-2:0], idata};
        end
        assign odata = sdata[SYNC_S-1];

    `else
        genvar gi;
        // for(gi=0; gi<DATA_W; gi++) begin
        //     macro_dsync sinst(
        //         .ck (oclk     ),
        //         .clb(orst_n   ),
        //         .d  (idata[gi]),
        //         .o  (odata[gi])
        //         );
        // end
        /* use stdcell dff */

    `endif
`endif

//------------------------------------------------------------------------------
// Report & Assertion.
//------------------------------------------------------------------------------
`ifdef COM_REPORT_ON
    `ifdef COM_CDC_AS_REG
        initial begin
            $warning("COM Warning: Use reg for cdc at %m");
        end
    `endif
`endif

endmodule
