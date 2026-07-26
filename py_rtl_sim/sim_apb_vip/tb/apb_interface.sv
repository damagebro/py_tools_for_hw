interface apb_interface #(
    parameter int APB_AW = 32,
    parameter int APB_DW = 32
);

localparam int APB_SW = APB_DW / 8;

logic [APB_AW-1:0] paddr;
logic [2:0]         pprot;
logic               psel;
logic               penable;
logic               pwrite;
logic [APB_DW-1:0]  pwdata;
logic [APB_SW-1:0]  pstrb;
logic [APB_DW-1:0]  prdata;
logic               pready;
logic               pslverr;

modport master (
    output paddr, output pprot, output psel, output penable, output pwrite,
    output pwdata, output pstrb, input prdata, input pready, input pslverr
);

modport slave (
    input paddr, input pprot, input psel, input penable, input pwrite,
    input pwdata, input pstrb, output prdata, output pready, output pslverr
);

endinterface
