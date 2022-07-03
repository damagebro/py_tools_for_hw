interface AhbTbIf
(
    input clk
);
    bit         hselx   ;
    bit         hready  ;
    bit  [31:0] haddr   ;
    bit  [1:0]  htrans  ;//0:idle, 1:busy, 2:nonseq, 3:seq
    bit         hwrite  ;
    bit  [2:0]  hsize   ;//bytelen = 2^size
    bit  [2:0]  hburst  ;//0:single, 1:incr
    bit  [3:0]  hprot   ;//tie 4'b0
    bit  [31:0] hwdata  ;

    bit  [31:0] hrdata     ;
    bit         hready_out ;
    bit         hresp      ;//0: OKAY, 1:ERROR

    clocking cb @ (posedge clk);
        output hready,htrans,hsize,hburst,hprot;
        output hselx,haddr,hwrite,hwdata;
        input  hrdata,hready_out,   hresp;
    endclocking
    modport tx(clocking cb);
endinterface //AhbTbIf
typedef virtual AhbTbIf.tx vAhbTbIf;