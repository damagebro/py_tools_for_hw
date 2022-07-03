/******************************************************************************
*
*  Authors:   dmg
*    Email:   dmg@sensetime.com
*     Date:   2019/11/25-15:03:12
*
*  Description:
*   example for ahb bus convert to csr;
*
*  Modify:
*  -
*
******************************************************************************/

//`include "com_csr_ahbl2csr.v"
//`include "com_cdc_hs.v"

`ifndef ip_ahb_top_v
`define ip_ahb_top_v
module ip_ahb_top #( parameter
    AHB_AW = 32,
    AHB_DW = 32
)
(
input  wire                     clk                 ,
input  wire                     rst_n               ,
input  wire                     clear               ,

input  wire                     HCLK                ,
input  wire                     HRESETn             ,

input  wire                     HSELx               ,
input  wire                     HREADY              ,
input  wire [AHB_AW-1:0]        HADDR               ,
input  wire [1:0]               HTRANS              ,
input  wire                     HWRITE              ,
input  wire [2:0]               HSIZE               ,
input  wire [2:0]               HBURST              ,
input  wire [3:0]               HPROT               ,
input  wire [AHB_DW-1:0]        HWDATA              ,

output wire [AHB_DW-1:0]        HRDATA              ,
output wire                     HREADYOUT           ,
output wire                     HRESP               //,//0: OKAY, 1:ERROR
);
//localparam-----------------------------------------------------------------
localparam CSR_AW = 20;
localparam CSR_DW = 32;
localparam CSR_SW = CSR_DW/8;
//reg  declare---------------------------------------------------------------
//wire declare---------------------------------------------------------------
com_csr_if #(.AW(CSR_AW), .DW(CSR_DW)) cu_csr_if_dmahb();
com_csr_if #(.AW(CSR_AW), .DW(CSR_DW)) cu_csr_if();
//statement------------------------------------------------------------------

com_csr_ahbl2csr #(
    .AW_AHB     ( AHB_AW     ), //32
    .DW_AHB     ( AHB_DW     ), //32
    .AW_CSR     ( CSR_AW     ), //16
    .DW_CSR     ( CSR_DW     )  //32
)u_com_csr_ahbl2csr
(
    .HCLK                 ( HCLK                 ), //i
    .HRESETn              ( HRESETn              ), //i

    .HSELx                ( HSELx                ), //i
    .HREADY               ( HREADY               ), //i
    .HADDR                ( HADDR                ), //i
    .HTRANS               ( HTRANS               ), //i
    .HWRITE               ( HWRITE               ), //i
    .HSIZE                ( HSIZE                ), //i
    .HBURST               ( HBURST               ), //i
    .HPROT                ( HPROT                ), //i
    .HWDATA               ( HWDATA               ), //i

    .HRDATA               ( HRDATA               ), //o
    .HREADYOUT            ( HREADYOUT            ), //o
    .HRESP                ( HRESP                ), //o

    .csr_txif             ( cu_csr_if_dmahb      )  //if
);


com_csr_cdc #(
    .AW         ( CSR_AW        ), //16
    .DW         ( CSR_DW        )  //32
)u_com_csr_cdc
(
    .clk_s                ( HCLK                 ), //i
    .rst_n_s              ( HRESETn              ), //i
    .clear_s              ( 1'b0                 ), //i
    .clk_d                ( clk                  ), //i
    .rst_n_d              ( rst_n                ), //i
    .clear_d              ( claer                ), //i

    .csr_rxif             ( cu_csr_if_dmahb      ), //if
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


endmodule //end of ip_ahb_top
`endif //end of ip_ahb_top_v

