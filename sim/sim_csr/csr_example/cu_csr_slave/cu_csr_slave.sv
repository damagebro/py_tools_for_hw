/******************************************************************************
*
*  Authors:   <someone>
*    Email:   <someone>@sensetime.com
*     Date:   2022/04/26-22:29:39
*
*  Description:
*  -
*
*  Modify:
*  -
*
******************************************************************************/

`ifndef cu_csr_slave_v
`define cu_csr_slave_v
module cu_csr_slave #( parameter
    AW = 16,
    DW = 32,
    SW = DW/8
)
(
input  wire                     clk                 ,
input  wire                     rst_n               ,
input  wire                     clear               ,

com_csr_if.slave                csr_rxif            ,
//cu_sta
input  wire [31:0]              cu_sta_versionD               ,
//cu_cfg1
output wire [11:0]              cu_cfg1_ntid_xR               ,
output wire [11:0]              cu_cfg1_ntid_yR               ,
output wire [5:0]               cu_cfg1_ntid_zR               ,
//cu_cfg2
output wire [31:0]              cu_cfg2_nctaid_xR             ,
//cu_cfg3
output wire [31:0]              cu_cfg3_nctaid_yR             ,
//cu_cfg4
output wire [31:0]              cu_cfg4_nctaid_zR             ,
//cu_cfg5
output wire [21:0][31:0]        cu_cfg5_paramR                ,
//cu_cfg6
output wire [31:0]              cu_cfg6_init_pcR              ,
//cu_cmd
output wire                     cu_cmd_kernel_startOEn        ,
output wire                     cu_cmd_kernel_startO          ,
//cu_dbg
input  wire [31:0]              cu_dbg_pc_valD                //,
);
//localparam-----------------------------------------------------------------
//reg  declare---------------------------------------------------------------
//wire declare---------------------------------------------------------------
wire                   csr_write        ;
wire [AW-1:0]          csr_addr         ;
wire [DW-1:0]          csr_wdata        ;
wire [SW-1:0]          csr_wstrb        ;
wire                   csr_valid        ;
wire                   csr_ready        ;
wire [DW-1:0]          csr_rdata        ;
assign csr_write   = csr_rxif.csr_write  ;
assign csr_addr    = csr_rxif.csr_addr   ;
assign csr_wdata   = csr_rxif.csr_wdata  ;
assign csr_wstrb   = csr_rxif.csr_wstrb  ;
assign csr_valid   = csr_rxif.csr_valid  ;
assign csr_rxif.csr_ready   = csr_ready  ;
assign csr_rxif.csr_rdata   = csr_rdata  ;

wire [AW-1:0] csr_offset_regs1_lo = 'h0   ;
wire [AW-1:0] csr_offset_regs1_hi = 'h404 ;
wire [AW-1:0] csr_offset_dmys1_lo = 'h404 ;

wire bcsr_regs1_sel = csr_valid && csr_addr>=csr_offset_regs1_lo && csr_addr<csr_offset_regs1_hi;
wire bcsr_dmys1_sel = csr_valid && csr_addr>=csr_offset_dmys1_lo;
wire bcsr_regs_sel = bcsr_regs1_sel;

wire             csr_valid_regs  = bcsr_regs_sel ? csr_valid : 1'b0;
wire [AW-1:0]    csr_addr_regs   = bcsr_regs_sel ? csr_addr  : {AW{1'b0}};
wire             csr_ready_regs  ;
wire [DW-1:0]    csr_rdata_regs  ;

//statement------------------------------------------------------------------

wire          csr_ready_dmy   = 1'b1;
wire [DW-1:0] csr_rdata_dmy  = {2{16'hdeaf}};
reg           rb_csr_ready;
reg  [DW-1:0] rb_csr_rddata;
always @*
begin
    if( bcsr_regs_sel )begin
        rb_csr_ready = csr_ready_regs;
        rb_csr_rddata= csr_rdata_regs;
    end
    else begin
        rb_csr_ready = csr_ready_dmy;
        rb_csr_rddata= csr_rdata_dmy;
    end
end
assign csr_ready = rb_csr_ready;
assign csr_rdata = rb_csr_rddata;

cu_csr_slave_reg #(
    .AW (AW),
    .DW (DW)
) u_cu_csr_slave_reg
(
    .clk                 ( clk                  ),
    .rst_n               ( rst_n                ),
    .clear               ( clear                ),

    .csr_write           ( csr_write            ),
    .csr_addr            ( csr_addr_regs        ),
    .csr_wdata           ( csr_wdata            ),
    .csr_wstrb           ( csr_wstrb            ),
    .csr_valid           ( csr_valid_regs       ),
    .csr_ready           ( csr_ready_regs       ),
    .csr_rdata           ( csr_rdata_regs       ),
    .cu_sta_versionD               ( cu_sta_versionD                ),
    .cu_cfg1_ntid_xR               ( cu_cfg1_ntid_xR                ),
    .cu_cfg1_ntid_yR               ( cu_cfg1_ntid_yR                ),
    .cu_cfg1_ntid_zR               ( cu_cfg1_ntid_zR                ),
    .cu_cfg2_nctaid_xR             ( cu_cfg2_nctaid_xR              ),
    .cu_cfg3_nctaid_yR             ( cu_cfg3_nctaid_yR              ),
    .cu_cfg4_nctaid_zR             ( cu_cfg4_nctaid_zR              ),
    .cu_cfg5_paramR                ( cu_cfg5_paramR                 ),
    .cu_cfg6_init_pcR              ( cu_cfg6_init_pcR               ),
    .cu_cmd_kernel_startOEn        ( cu_cmd_kernel_startOEn         ),
    .cu_cmd_kernel_startO          ( cu_cmd_kernel_startO           ),
    .cu_dbg_pc_valD                ( cu_dbg_pc_valD                 )//,
);

endmodule //end of cu_csr_slave
`endif //end of cu_csr_slave_v