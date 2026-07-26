module sample_rtl #(
    parameter DW = 32
)(
    input  wire          clk,
    input  logic         i_valid,
    input  logic [DW-1:0] i_data,
    output logic         o_ready,
    output reg  [DW-1:0] o_data,
    inout  wire          io_pad
);

parameter DEPTH = 4;

endmodule
