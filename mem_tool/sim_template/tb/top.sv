module top();

bit clk   ;
bit rst_n ;
bit clear ;

always #2   clk= ~clk;

task reset();
    #10; rst_n = 1'b1;
    #15; rst_n = 1'b0;
    #20; rst_n = 1'b1;
endtask //reset_isp
task xclear();
    @( posedge clk ); clear <= 1'b0;
    @( posedge clk ); clear <= 1'b1;
    @( posedge clk ); clear <= 1'b0;
endtask //reset_isp


//-------------------------------------------------------
//dut
//-------------------------------------------------------
com_dummy u_com_dummy();
// cpu_dummy u_cpu_dummy();

// import FifoPkg::*;
// FifoIf fifo_if( clk );
// fifo_test fifo_t1( fifo_if );
// com_sync_fifo_reg #(
//     .DW         ( FIFO_DW         ), //8
//     .DEPTH      ( FIFO_DEPTH      )  //4
// )u_com_sync_fifo_reg
// (
//     .clk                  ( clk                  ), //i
//     .rst_n                ( rst_n                ), //i
//     .clear                ( clear                ), //i

//     .wr_en                ( fifo_if.wr_en        ), //i
//     .wr_data              ( fifo_if.wr_data      ), //i
//     .wr_full              ( fifo_if.wr_full      ), //o
//     .rd_en                ( fifo_if.rd_en        ), //i
//     .rd_data              ( fifo_if.rd_data      ), //o
//     .rd_empty             ( fifo_if.rd_empty     ), //o
//     .water_level          (                      )  //o
// );
//-------------------------------------------------------
//dump fsdb
//-------------------------------------------------------
initial begin
    #100;
    $finish();
end
`ifdef DUMP_FSDB
initial begin
    $fsdbDumpfile("run.fsdb");
    $fsdbDumpMDA(0,top)  ;   //dump array
    $fsdbDumpvars(0,top) ;  //dump struct
    $fsdbDumpvars(top,"+all");  //dump struct
    $fsdbDumpon();
end
`endif

endmodule
