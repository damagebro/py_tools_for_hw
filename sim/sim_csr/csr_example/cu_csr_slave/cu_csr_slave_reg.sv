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

`ifndef cu_csr_slave_reg_v
`define cu_csr_slave_reg_v
module cu_csr_slave_reg #( parameter
    AW = 16,
    DW = 32,
    SW = DW/8
)
(
input  wire                     clk                 ,
input  wire                     rst_n               ,
input  wire                     clear               ,

input  wire                     csr_write           ,
input  wire [AW-1:0]            csr_addr            ,
input  wire [DW-1:0]            csr_wdata           ,
input  wire [SW-1:0]            csr_wstrb           ,
input  wire                     csr_valid           ,
output wire                     csr_ready           ,
output wire [DW-1:0]            csr_rdata           ,
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
wire [AW-1:0] cu_sta_offset = 'h0;
wire [AW-1:0] cu_cfg1_offset = 'h100;
wire [AW-1:0] cu_cfg2_offset = 'h104;
wire [AW-1:0] cu_cfg3_offset = 'h108;
wire [AW-1:0] cu_cfg4_offset = 'h10c;
wire [21:0][AW-1:0] cu_cfg5_offset;
assign cu_cfg5_offset[0] = 'h110;
assign cu_cfg5_offset[1] = 'h114;
assign cu_cfg5_offset[2] = 'h118;
assign cu_cfg5_offset[3] = 'h11c;
assign cu_cfg5_offset[4] = 'h120;
assign cu_cfg5_offset[5] = 'h124;
assign cu_cfg5_offset[6] = 'h128;
assign cu_cfg5_offset[7] = 'h12c;
assign cu_cfg5_offset[8] = 'h130;
assign cu_cfg5_offset[9] = 'h134;
assign cu_cfg5_offset[10] = 'h138;
assign cu_cfg5_offset[11] = 'h13c;
assign cu_cfg5_offset[12] = 'h140;
assign cu_cfg5_offset[13] = 'h144;
assign cu_cfg5_offset[14] = 'h148;
assign cu_cfg5_offset[15] = 'h14c;
assign cu_cfg5_offset[16] = 'h150;
assign cu_cfg5_offset[17] = 'h154;
assign cu_cfg5_offset[18] = 'h158;
assign cu_cfg5_offset[19] = 'h15c;
assign cu_cfg5_offset[20] = 'h160;
assign cu_cfg5_offset[21] = 'h164;
wire [AW-1:0] cu_cfg6_offset = 'h190;
wire [AW-1:0] cu_cmd_offset = 'h200;
wire [AW-1:0] cu_dbg_offset = 'h400;
//statement------------------------------------------------------------------

//cu_cfg1
wire cu_cfg1_upen = (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg1_offset;
reg  [11:0] rccu_cfg1_ntid_x;
reg  [11:0] rccu_cfg1_ntid_y;
reg  [5:0] rccu_cfg1_ntid_z;
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n ) begin
        rccu_cfg1_ntid_x <= 'h400;
    end
    else if( clear ) begin
        rccu_cfg1_ntid_x <= 'h400;
    end
    else if( cu_cfg1_upen ) begin
        if( csr_wstrb[0] )
            rccu_cfg1_ntid_x[7:0] <= csr_wdata[7:0];
        if( csr_wstrb[1] )
            rccu_cfg1_ntid_x[11:8] <= csr_wdata[11:8];
    end
end
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n ) begin
        rccu_cfg1_ntid_y <= 'h1;
    end
    else if( clear ) begin
        rccu_cfg1_ntid_y <= 'h1;
    end
    else if( cu_cfg1_upen ) begin
        if( csr_wstrb[1] )
            rccu_cfg1_ntid_y[3:0] <= csr_wdata[15:12];
        if( csr_wstrb[2] )
            rccu_cfg1_ntid_y[11:4] <= csr_wdata[23:16];
    end
end
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n ) begin
        rccu_cfg1_ntid_z <= 'h1;
    end
    else if( clear ) begin
        rccu_cfg1_ntid_z <= 'h1;
    end
    else if( cu_cfg1_upen ) begin
        if( csr_wstrb[3] )
            rccu_cfg1_ntid_z[5:0] <= csr_wdata[29:24];
    end
end
assign cu_cfg1_ntid_xR = rccu_cfg1_ntid_x;
assign cu_cfg1_ntid_yR = rccu_cfg1_ntid_y;
assign cu_cfg1_ntid_zR = rccu_cfg1_ntid_z;

//cu_cfg2
wire cu_cfg2_upen = (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg2_offset;
reg  [31:0] rccu_cfg2_nctaid_x;
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n ) begin
        rccu_cfg2_nctaid_x <= 'h1;
    end
    else if( clear ) begin
        rccu_cfg2_nctaid_x <= 'h1;
    end
    else if( cu_cfg2_upen ) begin
        if( csr_wstrb[0] )
            rccu_cfg2_nctaid_x[7:0] <= csr_wdata[7:0];
        if( csr_wstrb[1] )
            rccu_cfg2_nctaid_x[15:8] <= csr_wdata[15:8];
        if( csr_wstrb[2] )
            rccu_cfg2_nctaid_x[23:16] <= csr_wdata[23:16];
        if( csr_wstrb[3] )
            rccu_cfg2_nctaid_x[31:24] <= csr_wdata[31:24];
    end
end
assign cu_cfg2_nctaid_xR = rccu_cfg2_nctaid_x;

//cu_cfg3
wire cu_cfg3_upen = (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg3_offset;
reg  [31:0] rccu_cfg3_nctaid_y;
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n ) begin
        rccu_cfg3_nctaid_y <= 'h1;
    end
    else if( clear ) begin
        rccu_cfg3_nctaid_y <= 'h1;
    end
    else if( cu_cfg3_upen ) begin
        if( csr_wstrb[0] )
            rccu_cfg3_nctaid_y[7:0] <= csr_wdata[7:0];
        if( csr_wstrb[1] )
            rccu_cfg3_nctaid_y[15:8] <= csr_wdata[15:8];
        if( csr_wstrb[2] )
            rccu_cfg3_nctaid_y[23:16] <= csr_wdata[23:16];
        if( csr_wstrb[3] )
            rccu_cfg3_nctaid_y[31:24] <= csr_wdata[31:24];
    end
end
assign cu_cfg3_nctaid_yR = rccu_cfg3_nctaid_y;

//cu_cfg4
wire cu_cfg4_upen = (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg4_offset;
reg  [31:0] rccu_cfg4_nctaid_z;
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n ) begin
        rccu_cfg4_nctaid_z <= 'h1;
    end
    else if( clear ) begin
        rccu_cfg4_nctaid_z <= 'h1;
    end
    else if( cu_cfg4_upen ) begin
        if( csr_wstrb[0] )
            rccu_cfg4_nctaid_z[7:0] <= csr_wdata[7:0];
        if( csr_wstrb[1] )
            rccu_cfg4_nctaid_z[15:8] <= csr_wdata[15:8];
        if( csr_wstrb[2] )
            rccu_cfg4_nctaid_z[23:16] <= csr_wdata[23:16];
        if( csr_wstrb[3] )
            rccu_cfg4_nctaid_z[31:24] <= csr_wdata[31:24];
    end
end
assign cu_cfg4_nctaid_zR = rccu_cfg4_nctaid_z;

//cu_cfg5
wire [21:0] cu_cfg5_upen;
assign cu_cfg5_upen[0]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[0];
assign cu_cfg5_upen[1]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[1];
assign cu_cfg5_upen[2]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[2];
assign cu_cfg5_upen[3]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[3];
assign cu_cfg5_upen[4]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[4];
assign cu_cfg5_upen[5]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[5];
assign cu_cfg5_upen[6]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[6];
assign cu_cfg5_upen[7]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[7];
assign cu_cfg5_upen[8]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[8];
assign cu_cfg5_upen[9]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[9];
assign cu_cfg5_upen[10]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[10];
assign cu_cfg5_upen[11]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[11];
assign cu_cfg5_upen[12]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[12];
assign cu_cfg5_upen[13]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[13];
assign cu_cfg5_upen[14]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[14];
assign cu_cfg5_upen[15]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[15];
assign cu_cfg5_upen[16]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[16];
assign cu_cfg5_upen[17]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[17];
assign cu_cfg5_upen[18]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[18];
assign cu_cfg5_upen[19]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[19];
assign cu_cfg5_upen[20]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[20];
assign cu_cfg5_upen[21]= (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg5_offset[21];
wire [21:0][31:0] cu_cfg5_param_default;
assign cu_cfg5_param_default[0]= 'h1;
assign cu_cfg5_param_default[1]= 'h1;
assign cu_cfg5_param_default[2]= 'h1;
assign cu_cfg5_param_default[3]= 'h1;
assign cu_cfg5_param_default[4]= 'h1;
assign cu_cfg5_param_default[5]= 'h1;
assign cu_cfg5_param_default[6]= 'h1;
assign cu_cfg5_param_default[7]= 'h1;
assign cu_cfg5_param_default[8]= 'h1;
assign cu_cfg5_param_default[9]= 'h1;
assign cu_cfg5_param_default[10]= 'h1;
assign cu_cfg5_param_default[11]= 'h1;
assign cu_cfg5_param_default[12]= 'h1;
assign cu_cfg5_param_default[13]= 'h1;
assign cu_cfg5_param_default[14]= 'h1;
assign cu_cfg5_param_default[15]= 'h1;
assign cu_cfg5_param_default[16]= 'h1;
assign cu_cfg5_param_default[17]= 'h1;
assign cu_cfg5_param_default[18]= 'h1;
assign cu_cfg5_param_default[19]= 'h1;
assign cu_cfg5_param_default[20]= 'h1;
assign cu_cfg5_param_default[21]= 'h1;
reg  [21:0][31:0] rccu_cfg5_param;
generate
for( genvar gi=0; gi<22; gi++ ) begin
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n ) begin
        rccu_cfg5_param[gi] <= cu_cfg5_param_default[gi];
    end
    else if( clear ) begin
        rccu_cfg5_param[gi] <= cu_cfg5_param_default[gi];
    end
    else if( cu_cfg5_upen[gi] ) begin
        if( csr_wstrb[0] )
            rccu_cfg5_param[gi][7:0] <= csr_wdata[7:0];
        if( csr_wstrb[1] )
            rccu_cfg5_param[gi][15:8] <= csr_wdata[15:8];
        if( csr_wstrb[2] )
            rccu_cfg5_param[gi][23:16] <= csr_wdata[23:16];
        if( csr_wstrb[3] )
            rccu_cfg5_param[gi][31:24] <= csr_wdata[31:24];
    end
end
end //end of for gi
endgenerate
assign cu_cfg5_paramR = rccu_cfg5_param;

//cu_cfg6
wire cu_cfg6_upen = (csr_valid && csr_ready) && csr_write && csr_addr==cu_cfg6_offset;
reg  [31:0] rccu_cfg6_init_pc;
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n ) begin
        rccu_cfg6_init_pc <= 'h1;
    end
    else if( clear ) begin
        rccu_cfg6_init_pc <= 'h1;
    end
    else if( cu_cfg6_upen ) begin
        if( csr_wstrb[0] )
            rccu_cfg6_init_pc[7:0] <= csr_wdata[7:0];
        if( csr_wstrb[1] )
            rccu_cfg6_init_pc[15:8] <= csr_wdata[15:8];
        if( csr_wstrb[2] )
            rccu_cfg6_init_pc[23:16] <= csr_wdata[23:16];
        if( csr_wstrb[3] )
            rccu_cfg6_init_pc[31:24] <= csr_wdata[31:24];
    end
end
assign cu_cfg6_init_pcR = rccu_cfg6_init_pc;

//cu_cmd
wire pscu_cmdWEn = (csr_valid && csr_ready) && csr_write && csr_addr==cu_cmd_offset;
assign cu_cmd_kernel_startOEn = pscu_cmdWEn;
assign cu_cmd_kernel_startO = csr_wdata[0];

//read reg
wire [DW-1:0] rddata_cu_sta = {cu_sta_versionD};
wire [DW-1:0] rddata_cu_cfg1 = {2'b0,cu_cfg1_ntid_zR,cu_cfg1_ntid_yR,cu_cfg1_ntid_xR};
wire [DW-1:0] rddata_cu_cfg2 = {cu_cfg2_nctaid_xR};
wire [DW-1:0] rddata_cu_cfg3 = {cu_cfg3_nctaid_yR};
wire [DW-1:0] rddata_cu_cfg4 = {cu_cfg4_nctaid_zR};
wire [21:0][DW-1:0] rddata_cu_cfg5;
assign rddata_cu_cfg5[0] = {cu_cfg5_paramR[0]};
assign rddata_cu_cfg5[1] = {cu_cfg5_paramR[1]};
assign rddata_cu_cfg5[2] = {cu_cfg5_paramR[2]};
assign rddata_cu_cfg5[3] = {cu_cfg5_paramR[3]};
assign rddata_cu_cfg5[4] = {cu_cfg5_paramR[4]};
assign rddata_cu_cfg5[5] = {cu_cfg5_paramR[5]};
assign rddata_cu_cfg5[6] = {cu_cfg5_paramR[6]};
assign rddata_cu_cfg5[7] = {cu_cfg5_paramR[7]};
assign rddata_cu_cfg5[8] = {cu_cfg5_paramR[8]};
assign rddata_cu_cfg5[9] = {cu_cfg5_paramR[9]};
assign rddata_cu_cfg5[10] = {cu_cfg5_paramR[10]};
assign rddata_cu_cfg5[11] = {cu_cfg5_paramR[11]};
assign rddata_cu_cfg5[12] = {cu_cfg5_paramR[12]};
assign rddata_cu_cfg5[13] = {cu_cfg5_paramR[13]};
assign rddata_cu_cfg5[14] = {cu_cfg5_paramR[14]};
assign rddata_cu_cfg5[15] = {cu_cfg5_paramR[15]};
assign rddata_cu_cfg5[16] = {cu_cfg5_paramR[16]};
assign rddata_cu_cfg5[17] = {cu_cfg5_paramR[17]};
assign rddata_cu_cfg5[18] = {cu_cfg5_paramR[18]};
assign rddata_cu_cfg5[19] = {cu_cfg5_paramR[19]};
assign rddata_cu_cfg5[20] = {cu_cfg5_paramR[20]};
assign rddata_cu_cfg5[21] = {cu_cfg5_paramR[21]};
wire [DW-1:0] rddata_cu_cfg6 = {cu_cfg6_init_pcR};
wire [DW-1:0] rddata_cu_dbg = {cu_dbg_pc_valD};

//flatten
wire [28:0][DW-1:0] a_rddata;
wire [28:0][AW-1:0] a_rdaddr;
assign a_rddata[0] = rddata_cu_sta;
assign a_rddata[1] = rddata_cu_cfg1;
assign a_rddata[2] = rddata_cu_cfg2;
assign a_rddata[3] = rddata_cu_cfg3;
assign a_rddata[4] = rddata_cu_cfg4;
assign a_rddata[26:5] = rddata_cu_cfg5;
assign a_rddata[27] = rddata_cu_cfg6;
assign a_rddata[28] = rddata_cu_dbg;

assign a_rdaddr[0] = cu_sta_offset;
assign a_rdaddr[1] = cu_cfg1_offset;
assign a_rdaddr[2] = cu_cfg2_offset;
assign a_rdaddr[3] = cu_cfg3_offset;
assign a_rdaddr[4] = cu_cfg4_offset;
assign a_rdaddr[26:5] = cu_cfg5_offset;
assign a_rdaddr[27] = cu_cfg6_offset;
assign a_rdaddr[28] = cu_dbg_offset;

//rden-------------
wire csr_rden = csr_valid && !csr_write;


//rdflag stage0
reg  [28:0] arbb_rdflag_s0;
always @*
begin
    for ( int i=0; i<29; i++ ) begin
        arbb_rdflag_s0[i] = csr_addr==a_rdaddr[i];
    end
end

//rbcsr_rddata
reg  [DW-1:0] rbcsr_rddata;
always @*
begin
    rbcsr_rddata = 'b0;
    if( csr_rden )begin
        for ( int i=0; i<29; i++ ) begin
            if( arbb_rdflag_s0[i] )begin
                rbcsr_rddata = a_rddata[i];
            end
        end
    end
end

//csr interface
assign csr_ready  = 1'b1;
assign csr_rdata = rbcsr_rddata;


endmodule //end of cu_csr_slave_reg
`endif //end of cu_csr_slave_reg_v