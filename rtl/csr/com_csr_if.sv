//--------------------------------------------------------------
interface com_csr_if;
    parameter  AW = 16;
    parameter  DW = 32;
    localparam SW = DW/8;

    wire                 csr_write ;
    wire [AW-1:0]        csr_addr  ;
    wire [DW-1:0]        csr_wdata ;
    wire [DW/8-1:0]      csr_wstrb ;
    wire                 csr_valid ;
    wire                 csr_ready ;
    wire [DW-1:0]        csr_rdata ;

    // wire                   bCSRWrite         ; //used name style before 2022
    // wire [AW-1:0]          CSRAddr           ;
    // wire [DW-1:0]          CSRWrData         ;
    // wire [SW-1:0]          CSRWrStrb         ;
    // wire                   CSRValid          ;
    // wire                   CSRReady          ;
    // wire [DW-1:0]          CSRRdData         ;

    modport master(
        input  csr_ready,csr_rdata,
        output csr_valid,csr_write,csr_addr,csr_wdata,csr_wstrb
        );

    modport slave(
        output csr_ready,csr_rdata,
        input  csr_valid,csr_write,csr_addr,csr_wdata,csr_wstrb
        );

    modport monitor(
        input csr_valid,csr_ready,csr_write
        );
endinterface