`timescale 1ns/1ps

import axi_vip_pkg::*;

module top();

localparam int AXI_AW = 32;
localparam int AXI_DW = 32;
localparam int AXI_IDW = 4;

logic clk;
logic rst_n;
logic master_done;
string cfg_file;
int timeout_cycle;

axi_interface #(
    .AXI_AW  (AXI_AW),
    .AXI_DW  (AXI_DW),
    .AXI_IDW (AXI_IDW)
) axi_bus();

initial begin
    clk = 1'b0;
    forever #5 clk = ~clk;
end

initial begin
    rst_n = 1'b0;
    repeat (10)
        @(posedge clk);
    rst_n = 1'b1;
end

initial begin
    if (!$value$plusargs("AXI_CFG=%s", cfg_file))
        cfg_file = "../axi_vip.cfg";
    timeout_cycle = cfg_get_int(cfg_file, "timeout_cycle", 20000);
    $display("[TOP] AXI_CFG=%s timeout_cycle=%0d", cfg_file, timeout_cycle);
end

axi_master #(
    .MASTER_ID (0),
    .AXI_AW     (AXI_AW),
    .AXI_DW     (AXI_DW),
    .AXI_IDW    (AXI_IDW)
) u_axi_master (
    .clk   (clk),
    .rst_n (rst_n),
    .done  (master_done),
    .m_axi (axi_bus)
);

axi_slave #(
    .SLAVE_ID (0),
    .AXI_AW   (AXI_AW),
    .AXI_DW   (AXI_DW),
    .AXI_IDW  (AXI_IDW)
) u_axi_slave (
    .clk   (clk),
    .rst_n (rst_n),
    .s_axi (axi_bus)
);

initial begin
    wait (rst_n == 1'b1);
    fork
        begin
            wait (master_done);
            repeat (20)
                @(posedge clk);
            $display("[TOP] AXI VIP PASS");
            $finish();
        end
        begin
            repeat (timeout_cycle)
                @(posedge clk);
            $fatal(1, "[TOP] timeout waiting AXI VIP done");
        end
    join_any
end

`ifdef DUMP_FSDB
initial begin
    $fsdbDumpfile("run.fsdb");
    $fsdbDumpMDA(0, top);
    $fsdbDumpvars(0, top);
    $fsdbDumpvars(top, "+all");
    $fsdbDumpon();
end
`endif

`ifdef DUMP_FST
initial begin
    $dumpfile("run.fst");
    $dumpvars(0, top);
end
`endif

endmodule
