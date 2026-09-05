module top();

// AUTO_TOP_INST_BEGIN
// AUTO_TOP_INST_END

initial begin
    #100;
    $finish();
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

endmodule
