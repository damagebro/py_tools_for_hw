interface axi_interface #(
    parameter int AXI_AW = 32,
    parameter int AXI_DW = 32,
    parameter int AXI_IDW = 4
);

localparam int AXI_SW = AXI_DW / 8;

logic [AXI_IDW-1:0] awid;
logic [AXI_AW-1:0]  awaddr;
logic [7:0]         awlen;
logic [2:0]         awsize;
logic [1:0]         awburst;
logic               awvalid;
logic               awready;

logic [AXI_DW-1:0]  wdata;
logic [AXI_SW-1:0]  wstrb;
logic               wlast;
logic               wvalid;
logic               wready;

logic [AXI_IDW-1:0] bid;
logic [1:0]         bresp;
logic               bvalid;
logic               bready;

logic [AXI_IDW-1:0] arid;
logic [AXI_AW-1:0]  araddr;
logic [7:0]         arlen;
logic [2:0]         arsize;
logic [1:0]         arburst;
logic               arvalid;
logic               arready;

logic [AXI_IDW-1:0] rid;
logic [AXI_DW-1:0]  rdata;
logic [1:0]         rresp;
logic               rlast;
logic               rvalid;
logic               rready;

modport master (
    output awid,
    output awaddr,
    output awlen,
    output awsize,
    output awburst,
    output awvalid,
    input  awready,
    output wdata,
    output wstrb,
    output wlast,
    output wvalid,
    input  wready,
    input  bid,
    input  bresp,
    input  bvalid,
    output bready,
    output arid,
    output araddr,
    output arlen,
    output arsize,
    output arburst,
    output arvalid,
    input  arready,
    input  rid,
    input  rdata,
    input  rresp,
    input  rlast,
    input  rvalid,
    output rready
);

modport slave (
    input  awid,
    input  awaddr,
    input  awlen,
    input  awsize,
    input  awburst,
    input  awvalid,
    output awready,
    input  wdata,
    input  wstrb,
    input  wlast,
    input  wvalid,
    output wready,
    output bid,
    output bresp,
    output bvalid,
    input  bready,
    input  arid,
    input  araddr,
    input  arlen,
    input  arsize,
    input  arburst,
    input  arvalid,
    output arready,
    output rid,
    output rdata,
    output rresp,
    output rlast,
    output rvalid,
    input  rready
);

endinterface
