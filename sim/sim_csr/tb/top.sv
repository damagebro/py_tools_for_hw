module top();

bit clk   ;
bit rst_n ;
bit clear ;
bit pclk   ;
bit prst_n ;

always #2   clk= ~clk;
always #3   pclk= ~pclk;

task reset();
    prst_n = 1'b0;
    #10; rst_n = 1'b1; prst_n = 1'b1;
    #15; rst_n = 1'b0;
    #20; rst_n = 1'b1;
endtask //reset_isp
task xclear();
    @( posedge clk ); clear <= 1'b0;
    @( posedge clk ); clear <= 1'b1;
    @( posedge clk ); clear <= 1'b0;
endtask //reset_isp


//-------------------------------------------------------
//apb2csr
//-------------------------------------------------------
// bit          psel     ;
// bit          penable  ;
// bit [31:0]   paddr    ;
// bit          pwrite   ;
// bit [31:0]   pwdata   ;
// bit [31:0]   prdata   ;
// bit          pready   ;

import ApbPkg::*;
ApbTbIf  apb_if( .clk(pclk) );
apb_test apb_t1( apb_if );

wire [2:0]      post_cfg1_post_ctlR           ;
wire            post_cfg2_img_widthR          ;
wire            post_cfg2_img_heighR          ;
wire [31:0]     post_cfg3_blc_scaleR          ;
wire [1:0]      post_cfg4_blc_scaleR          ;
wire [31:0]     post_cfg5_ddr_wbaseR          ;
wire [31:0]     post_cfg6_patch_strideR       ;
wire [15:0]     post_cfg7_ddr_strideR         ;
wire [31:0]     post_dbg_patch_statD          ;
ip_apb_top u_ip_apb_top
(
    .clk                  ( clk                  ), //i
    .rst_n                ( rst_n                ), //i
    .clear                ( clear                ), //i

    .PCLK                 ( pclk                 ), //i
    .PRESETn              ( prst_n               ), //i

    .PADDR                ( apb_if.paddr         ), //i
    .PSELx                ( apb_if.psel          ), //i
    .PENABLE              ( apb_if.penable       ), //i
    .PWRITE               ( apb_if.pwrite        ), //i
    .PWDATA               ( apb_if.pwdata        ), //i
    .PSTRB                ( 4'hf          ), //i
    .PPROT                ( 3'b001        ), //i

    .PREADY               ( apb_if.pready        ), //o
    .PRDATA               ( apb_if.prdata        ), //o
    .PSLVERR              (                      )  //o
);

//-------------------------------------------------------
//ahb2csr
//-------------------------------------------------------
AhbTbIf  ahb_if( .clk(pclk) );
ahb_test ahb_t1( ahb_if );
ip_ahb_top u_ip_ahb_top
(
    .clk                  ( clk                  ), //i
    .rst_n                ( rst_n                ), //i
    .clear                ( clear                ), //i

    .HCLK                 ( pclk                 ), //i
    .HRESETn              ( prst_n               ), //i

    .HSELx                ( ahb_if.hselx         ), //i
    .HREADY               ( ahb_if.hready        ), //i
    .HADDR                ( ahb_if.haddr         ), //i
    .HTRANS               ( ahb_if.htrans        ), //i
    .HWRITE               ( ahb_if.hwrite        ), //i
    .HSIZE                ( ahb_if.hsize         ), //i
    .HBURST               ( ahb_if.hburst        ), //i
    .HPROT                ( ahb_if.hprot         ), //i
    .HWDATA               ( ahb_if.hwdata        ), //i

    .HRDATA               ( ahb_if.hrdata        ), //o
    .HREADYOUT            ( ahb_if.hready_out    ), //o
    .HRESP                ( ahb_if.hresp         )  //o
);

//-------------------------------------------------------
//dump fsdb
//-------------------------------------------------------
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
