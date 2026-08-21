# RTL 代码片段

本文件是 `py_rtl_snippet` 的唯一片段源。每个二级标题是 VS Code 的触发前缀；标题下的 `title`、`description`、`scope` 为元数据；紧随其后的 SystemVerilog 代码块为实际插入内容。

## rtl-module

- title: RTL module
- description: Module header with parameter, ports, and code sections.
- scope: systemverilog,verilog

```systemverilog
module ${1:module_name} #(
    parameter PIPE_NUM = 1,  //range=[1::]
    parameter DW = 8 //,
)
(
    input  logic                    clk          ,
    input  logic                    rst_n        ,

    input  logic [DW-1:0]           i_rx_payload ,
    output logic [DW-1:0]           o_tx_payload //,
);

//localparam-----------------------------------------------------------------
//signal declare-------------------------------------------------------------
logic [PIPE_NUM-1:0] r_flag;
logic [PIPE_NUM-1:0][DW-1:0] r_payload;
//statement------------------------------------------------------------------
//output assign---
assign o_tx_payload = r_payload[NUM_STG-1];

//body----
always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        r_flag <= '0;
    else if( xx )
        r_flag <= '0;
end

//instance----
assign u_xx_i_port1 = i_rx_payload;
abc #(
    .DW  (XX_DW)   //default: 16
)u_abc_xx
(
    .i_port1   (u_xx_i_port1), //i
    .o_port2   (u_xx_o_port2), //o
    ...
);

endmodule
```

## rtl-always

- title: RTL clocked always
- description: Clocked always block.

```systemverilog
always @(posedge clk) begin
    if( xx )
        r_flag <= '0;
end
```

## rtl-dff-an

- title: RTL DFF async reset
- description: DFF with active-low asynchronous reset.

```systemverilog
always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        r_flag <= '0;
    else if( xx )
        r_flag <= '0;
end
```

## rtl-dff

- title: RTL DFF async reset, with if(xx) begin end
- description: DFF with active-low asynchronous reset.

```systemverilog
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        r_flag <= '0;
    end
    else if( xx ) begin
        r_flag <= '0;
    end
end
```

## rtl-comb

- title: RTL combinational always
- description: Combinational always block.

```systemverilog
always @* begin
    w_xx = '0;
end
```

## rtl-struct

- title: RTL packed struct
- description: Packed struct typedef with _ts suffix.

```systemverilog
typedef struct packed {
    logic [${1:31}:0] ${2:data};
    logic            ${3:valid};
} ${4:data_ts};${0}
```

## rtl-union

- title: RTL packed union
- description: Packed union typedef with _tu suffix.

```systemverilog
typedef union packed {
    logic [${1:31}:0] ${2:data};
    ${3:data_ts}     ${4:payload};
} ${5:data_tu};${0}
```

## rtl-enum

- title: RTL enum
- description: Enum typedef with e_ item prefix and _te suffix.

```systemverilog
typedef enum logic [${1:1}:0] {
    e_${2:IDLE} = ${3:2'd0},
    e_${4:RUN}  = ${5:2'd1}
} ${6:state_te};${0}
```

## vld-rdy-port

- title: Valid-ready ports
- description: Valid-ready receive and transmit port group.

```systemverilog
input  logic [DW-1:0]      i_rx_payload ,
input  logic               i_rx_valid   ,
output logic               o_rx_ready   ,

output logic [DW-1:0]      o_tx_payload ,
output logic               o_tx_valid   ,
input  logic               i_tx_ready   ,
```

## ram-port

- title: RAM ports
- description: Single-port RAM request and response port group.

```systemverilog
parameter AW           = 8,
parameter DW           = 8,
parameter STRB_W       = 1, //range=[1::] //DW%STRB_W==0,  SUB_DW = DW/STRB_W
//port signal---
input  wire [AW-1:0]       i_rx_wr_addr  ,
input  wire [DW-1:0]       i_rx_wr_data  ,
input  wire [STRB_W-1:0]   i_rx_wr_vld   ,
output wire                o_rx_wr_rdy   ,
input  wire [AW-1:0]       i_rx_rd_addr  ,
input  wire                i_rx_rd_vld   ,
output wire                o_rx_rd_rdy   ,
output wire                o_rx_rd_ack   ,
output wire [DW-1:0]       o_rx_rd_data  ,
```

## csr-port

- title: CSR ports
- description: CSR request and response port group.

```systemverilog
input  wire                         i_rx_csr_req_write   ,
input  wire [CSR_AW-1:0]            i_rx_csr_req_addr    ,
input  wire [CSR_DW-1:0]            i_rx_csr_req_wdata   ,
input  wire [CSR_DW/8-1:0]          i_rx_csr_req_wstrb   ,
input  wire                         i_rx_csr_req_valid   ,
output wire                         o_rx_csr_req_ready   ,
output wire                         o_rx_csr_rsp_rvalid  ,
output wire [CSR_DW-1:0]            o_rx_csr_rsp_rdata   ,
```

## ebus-rdport

- title: eBus read ports
- description: eBus read request and response port group.

```systemverilog
input  wire [UW-1:0]            i_rx_ebus_ra_user    ,
input  wire [AW-1:0]            i_rx_ebus_ra_addr    ,
input  wire [EBUS_LW-1:0]       i_rx_ebus_ra_bytelen ,
input  wire                     i_rx_ebus_ra_valid   ,
output wire                     o_rx_ebus_ra_ready   ,
output wire [DW-1:0]            o_rx_ebus_rd_data    ,
output wire                     o_rx_ebus_rd_last    ,
output wire                     o_rx_ebus_rd_valid   ,
input  wire                     i_rx_ebus_rd_ready   ,
```

## ebus-wrport

- title: eBus write ports
- description: eBus write request and response port group.

```systemverilog
input  wire [UW-1:0]            i_rx_ebus_wa_user    ,
input  wire [AW-1:0]            i_rx_ebus_wa_addr    ,
input  wire [EBUS_LW-1:0]       i_rx_ebus_wa_bytelen ,
input  wire                     i_rx_ebus_wa_valid   ,
output wire                     o_rx_ebus_wa_ready   ,
input  wire [DW-1:0]            i_rx_ebus_wd_data    ,
input  wire                     i_rx_ebus_wd_valid   ,
output wire                     o_rx_ebus_wd_ready   ,
output wire                     o_rx_ebus_wb_valid   ,
```

## apb-port

- title: APB ports
- description: APB slave port group without clock and reset.

```systemverilog
input  logic [${1:APB_AW}-1:0]  i_apb_paddr   ,
input  logic [${2:APB_DW}-1:0]  i_apb_pwdata  ,
input  logic [${2}/8-1:0]       i_apb_pstrb   ,
input  logic                    i_apb_pwrite  ,
input  logic                    i_apb_psel    ,
input  logic                    i_apb_penable ,
output logic                    o_apb_pready  ,
output logic [${2}-1:0]         o_apb_prdata  ,
output logic                    o_apb_pslverr ,
```

## axi4-port

- title: AXI4 ports
- description: AXI4 slave port group with all mandatory five-channel signals.

```systemverilog

output wire [IW-1:0]            o_tx_axi_awid    ,
output wire [AW-1:0]            o_tx_axi_awaddr  ,
output wire [LW-1:0]            o_tx_axi_awlen   ,
output wire [UW-1:0]            o_tx_axi_awuser  ,
output wire                     o_tx_axi_awvalid ,
input  wire                     i_tx_axi_awready ,
output wire [DW-1:0]            o_tx_axi_wdata   ,
output wire [DW/8-1:0]          o_tx_axi_wstrb   ,
output wire                     o_tx_axi_wlast   ,
output wire                     o_tx_axi_wvalid  ,
input  wire                     i_tx_axi_wready  ,
input  wire [1:0]               i_tx_axi_bresp   , //0:OKAY, 1:EXOKAY, 2:SVLERR, 3:DECERR
input  wire [IW-1:0]            i_tx_axi_bid     ,
input  wire                     i_tx_axi_bvalid  ,
output wire                     o_tx_axi_bready  ,

output wire [IW-1:0]            o_tx_axi_arid    ,
output wire [AW-1:0]            o_tx_axi_araddr  ,
output wire [LW-1:0]            o_tx_axi_arlen   ,
output wire [UW-1:0]            o_tx_axi_aruser  ,
output wire                     o_tx_axi_arvalid ,
input  wire                     i_tx_axi_arready ,
input  wire [1:0]               i_tx_axi_rresp   , //0:OKAY, 1:EXOKAY, 2:SVLERR, 3:DECERR
input  wire [IW-1:0]            i_tx_axi_rid     ,
input  wire [DW-1:0]            i_tx_axi_rdata   ,
input  wire                     i_tx_axi_rlast   ,
input  wire                     i_tx_axi_rvalid  ,
output wire                     o_tx_axi_rready  ,
```
