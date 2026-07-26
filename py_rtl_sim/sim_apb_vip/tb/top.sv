`timescale 1ns/1ps

import apb_vip_pkg::*;

module top();

localparam int APB_AW = 32;
localparam int APB_DW = 32;

reg clk;
reg rst_n;
reg done;
string cfg_file;
int timeout_cycle;

apb_interface #(
    .APB_AW (APB_AW),
    .APB_DW (APB_DW)
) apb_bus();

initial begin
    clk = 1'b0;
    forever #5 clk = ~clk;
end

initial begin
    rst_n = 1'b0;
    repeat (10) @(posedge clk);
    rst_n = 1'b1;
end

initial begin
    if (!$value$plusargs("APB_CFG=%s", cfg_file))
        cfg_file = "../apb_vip.cfg";
    timeout_cycle = cfg_get_uint(cfg_file, "timeout_cycle", 20000);
    $display("[TOP] APB_CFG=%s timeout_cycle=%0d", cfg_file, timeout_cycle);
end

assign apb_bus.prdata  = apb_bus.paddr;
assign apb_bus.pready  = 1'b1;
assign apb_bus.pslverr = 1'b0;

apb_master #(
    .MASTER_ID (0),
    .APB_AW   (APB_AW),
    .APB_DW   (APB_DW)
) u_apb_master (
    .clk   (clk),
    .rst_n (rst_n),
    .done  (done),
    .m_apb (apb_bus)
);

initial begin
    wait (rst_n == 1'b1);
    fork
        begin
            wait (done);
            repeat (5) @(posedge clk);
            $display("[TOP] APB VIP PASS");
            $finish();
        end
        begin
            repeat (timeout_cycle) @(posedge clk);
            $fatal(1, "[TOP] timeout waiting APB VIP done");
        end
    join_any
end

`ifdef DUMP_FSDB
initial begin
    $fsdbDumpfile("run.fsdb");
    $fsdbDumpvars(0, top);
    $fsdbDumpon();
end
`endif

endmodule
