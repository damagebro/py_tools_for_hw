interface ahb_interface #(
    parameter int AHB_AW = 32,
    parameter int AHB_DW = 32
);

logic [AHB_AW-1:0] haddr;
logic [1:0]        htrans;
logic              hwrite;
logic [2:0]        hsize;
logic [2:0]        hburst;
logic [3:0]        hprot;
logic [AHB_DW-1:0] hwdata;
logic [AHB_DW-1:0] hrdata;
logic              hready;
logic [1:0]        hresp;

modport master (
    output haddr, output htrans, output hwrite, output hsize,
    output hburst, output hprot, output hwdata,
    input hrdata, input hready, input hresp
);

modport slave (
    input haddr, input htrans, input hwrite, input hsize,
    input hburst, input hprot, input hwdata,
    output hrdata, output hready, output hresp
);

endinterface
