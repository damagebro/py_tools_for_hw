/******************************************************************************
*
*  Authors:   dmg
*    Email:   dmg@sensetime.com
*     Date:   2019/11/25-17:26:55
*
*  Description:
*   example for apb bus convert to csr;
*
*  Modify:
*  -
*
******************************************************************************/

`ifndef ip_apb_top_v
`define ip_apb_top_v
module ip_apb_top #( parameter
    APB_AW = 32,
    APB_DW = 32,
    APB_SW = APB_DW/8
)
(
input  wire                     clk                 ,
input  wire                     rst_n               ,
input  wire                     clear               ,

input  wire                     PCLK                ,
input  wire                     PRESETn             ,

input  wire [APB_AW-1:0]        PADDR               ,
input  wire [2:0]               PPROT               , //3'b001, [0]normal/privileged, [1]secure/nonsecure, [2]data/instruction;  0/1
input  wire                     PSELx               ,
input  wire                     PENABLE             ,
input  wire                     PWRITE              ,
input  wire [APB_DW-1:0]        PWDATA              ,
input  wire [APB_SW-1:0]        PSTRB               ,

output wire                     PREADY              ,
output wire [APB_DW-1:0]        PRDATA              ,
output wire                     PSLVERR             //,
);
//localparam-----------------------------------------------------------------
localparam CSR_AW = 20;
localparam CSR_DW = 32;
localparam CSR_SW = CSR_DW/8;
//reg  declare---------------------------------------------------------------
//wire declare---------------------------------------------------------------
com_csr_if #(.AW(CSR_AW), .DW(CSR_DW)) cu_csr_if_dmapb();
com_csr_if #(.AW(CSR_AW), .DW(CSR_DW)) cu_csr_if();
//statement------------------------------------------------------------------

com_csr_apb2csr #(
    .AW_APB     ( APB_AW     ), //32
    .DW_APB     ( APB_DW     ), //32
    .AW_CSR     ( CSR_AW     )  //16
)u_com_csr_apb2csr
(
    .PCLK                 ( PCLK                 ), //i
    .PRESETn              ( PRESETn              ), //i

    .PADDR                ( PADDR                ), //i
    .PPROT                ( PPROT                ), //i
    .PSELx                ( PSELx                ), //i
    .PENABLE              ( PENABLE              ), //i
    .PWRITE               ( PWRITE               ), //i
    .PWDATA               ( PWDATA               ), //i
    .PSTRB                ( PSTRB                ), //i

    .PREADY               ( PREADY               ), //o
    .PRDATA               ( PRDATA               ), //o
    .PSLVERR              ( PSLVERR              ), //o

    .csr_txif             ( cu_csr_if_dmapb      )  //if
);
com_csr_cdc #(
    .AW         ( CSR_AW        ), //16
    .DW         ( CSR_DW        )  //32
)u_com_csr_cdc
(
    .clk_s                ( PCLK                 ), //i
    .rst_n_s              ( PRESETn              ), //i
    .clear_s              ( 1'b0                 ), //i
    .clk_d                ( clk                  ), //i
    .rst_n_d              ( rst_n                ), //i
    .clear_d              ( clear                ), //i

    .csr_rxif             ( cu_csr_if_dmapb      ), //if
    .csr_txif             ( cu_csr_if            )  //if
);


//cu_csr_slave--------------------
wire [31:0]     cu_sta_versionD               = 32'h20_1028_0a;
wire [11:0]     cu_cfg1_ntid_xR               ;
wire [11:0]     cu_cfg1_ntid_yR               ;
wire [5:0]      cu_cfg1_ntid_zR               ;
wire [31:0]     cu_cfg2_nctaid_xR             ;
wire [31:0]     cu_cfg3_nctaid_yR             ;
wire [31:0]     cu_cfg4_nctaid_zR             ;
wire [21:0][31:0] cu_cfg5_paramR              ;
wire [31:0]     cu_cfg6_init_pcR              ;
wire            cu_cmd_kernel_startOEn        ;
wire            cu_cmd_kernel_startO          ;
wire [31:0]     cu_dbg_pc_valD                = 32'h1000;
cu_csr_slave #(
    .AW         ( CSR_AW      ), //16
    .DW         ( CSR_DW      )  //32
)u_cu_csr_slave
(
    .clk                  ( clk                  ), //i
    .rst_n                ( rst_n                ), //i
    .clear                ( clear                ), //i

    .csr_rxif             ( cu_csr_if            ), //if

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


endmodule //end of ip_apb_top
`endif //end of ip_apb_top_v

