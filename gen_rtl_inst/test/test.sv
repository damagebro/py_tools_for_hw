package sample_pkg;
    typedef struct packed {
        logic [7:0] data;
        logic       last;
    } payload_ts;
endpackage

interface axi_lite_if;
    logic valid;
    logic ready;
    modport master(output valid, input ready);
endinterface

module sample_sv #(
    parameter DW = 32,
    parameter type PAYLOAD_T = sample_pkg::payload_ts,
    parameter LANES = 2
)
(
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         core_clk,
    input  wire                         bus_rst_n,
    input  logic [LANES-1:0][DW-1:0]    i_rx_data,
    output sample_pkg::payload_ts       o_tx_payload,
    output logic [DW-1:0]               tx_data [LANES],
    axi_lite_if.master                  m_axi
);

localparam AW = $clog2(DW);
localparam HIDDEN = 1;
parameter EXTRA = AW + 1;

endmodule

module sample_v95(clk, rst_n, req, gnt, pad);
parameter DW = 8;
localparam SKIP_ME = 4;
parameter AW = 3;

input clk;
input rst_n;
input [DW-1:0] req;
output [DW-1:0] gnt;
inout pad;

endmodule
