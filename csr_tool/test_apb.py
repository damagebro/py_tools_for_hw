from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from src.models import BaseInfoModel, ModuleModel
from src.reg_gen_rtl import _apb_rtl


@unittest.skipUnless(shutil.which("iverilog") and shutil.which("vvp"), "Icarus is required")
class APBSimulationTests(unittest.TestCase):
    def test_wait_states_and_back_to_back_access(self):
        for protocol in ("apb3", "apb4"):
            with self.subTest(protocol=protocol), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                model = ModuleModel("sample", "sample.md", BaseInfoModel(protocol=protocol))
                (root / "wrapper.sv").write_text(_apb_rtl(model), encoding="utf-8")
                extra = ".i_apb_pstrb(4'b0101), .i_apb_pprot(3'b001)," if protocol == "apb4" else ""
                strobe = "4'b0101" if protocol == "apb4" else "4'b1111"
                bench = r"""
module sample #(parameter CSR_AW=32, CSR_DW=32)(
input clk, rst_n, clear, i_csr_req_write, i_csr_req_valid,
input [CSR_AW-1:0] i_csr_req_addr,
input [CSR_DW-1:0] i_csr_req_wdata,
input [CSR_DW/8-1:0] i_csr_req_wstrb,
output wire o_csr_req_ready,
output reg [CSR_DW-1:0] o_csr_rsp_rdata,
output reg o_csr_rsp_rvalid);
integer writes=0, reads=0, delay_count=0, wait_count=0;
reg [3:0] last_strobe;
assign o_csr_req_ready = wait_count >= 2;
always @(posedge clk) begin
    if (!rst_n || clear) begin
        wait_count <= 0;
        delay_count <= 0;
        o_csr_rsp_rvalid <= 0;
    end else begin
        wait_count <= wait_count + 1;
        o_csr_rsp_rvalid <= 0;
        if (delay_count > 0) begin
            delay_count <= delay_count - 1;
            if (delay_count == 1) begin
                o_csr_rsp_rvalid <= 1;
                o_csr_rsp_rdata <= 32'h12345678;
            end
        end
        if (i_csr_req_valid && o_csr_req_ready) begin
            wait_count <= 0;
            if (i_csr_req_write) begin
                writes <= writes + 1;
                last_strobe <= i_csr_req_wstrb;
            end else begin
                reads <= reads + 1;
                delay_count <= 3;
            end
        end
    end
end
endmodule

module tb;
reg clk=0, rst_n=0, clear=0, sel=0, enable=0, wr=0;
wire ready, err;
wire [31:0] data;
always #5 clk=~clk;
sample_apb dut(.clk(clk), .rst_n(rst_n), .clear(clear),
 .i_apb_paddr(32'h0), .i_apb_psel(sel), .i_apb_penable(enable),
 .i_apb_pwrite(wr), .i_apb_pwdata(32'h55), EXTRA
 .o_apb_pready(ready), .o_apb_prdata(data), .o_apb_pslverr(err));
task access(input bit write_access);
begin
    @(negedge clk); sel=1; enable=0; wr=write_access;
    @(negedge clk); enable=1;
    @(posedge clk);
    while (!ready) @(posedge clk);
    if (err) $fatal(1, "unexpected error");
    if (!write_access && data !== 32'h12345678) $fatal(1, "bad read data");
    @(negedge clk); enable=0;
end
endtask
initial begin
    repeat(2) @(negedge clk);
    rst_n=1;
    access(1); access(0); access(0); access(1);
    sel=0;
    repeat(3) @(negedge clk);
    if (dut.u_sample.writes != 2 || dut.u_sample.reads != 2)
        $fatal(1, "duplicate or missing CSR request");
    if (dut.u_sample.last_strobe !== STROBE) $fatal(1, "bad strobe");
    $display("PASS"); $finish;
end
initial begin #2000; $fatal(1, "timeout"); end
endmodule
""".replace("EXTRA", extra).replace("STROBE", strobe)
                (root / "tb.sv").write_text(bench, encoding="utf-8")
                result = subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", str(root / "test.vvp"), str(root / "wrapper.sv"), str(root / "tb.sv")], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                result = subprocess.run(["vvp", str(root / "test.vvp")], capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
