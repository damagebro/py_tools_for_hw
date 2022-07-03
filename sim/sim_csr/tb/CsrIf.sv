interface ApbTbIf
(
    input clk
);
    import ApbPkg::*;

    bit          psel     ;
    bit          penable  ;
    bit [31:0]   paddr    ;
    bit          pwrite   ;
    bit [31:0]   pwdata   ;
    bit [31:0]   prdata   ;
    bit          pready   ;


    clocking cb @ (posedge clk);
        output psel,penable, paddr,pwrite,pwdata;
        input  prdata, pready;
    endclocking
    modport tx(clocking cb);
endinterface //ApbTbIf
typedef virtual ApbTbIf.tx vApbTbIf;