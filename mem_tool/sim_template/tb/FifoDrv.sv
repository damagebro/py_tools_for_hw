package FifoPkg;
localparam FIFO_DW    = 16;
localparam FIFO_DEPTH = 4;
localparam FIFO_AW    = $clog2(FIFO_DEPTH>2?FIFO_DEPTH:2);
endpackage
interface FifoIf(
    input clk
);
    import FifoPkg::*;

    logic                     wr_en               ;
    logic [FIFO_DW-1:0]       wr_data             ;
    logic                     wr_full             ;
    logic                     rd_en               ;
    logic [FIFO_DW-1:0]       rd_data             ;
    logic                     rd_empty            ;


    clocking cb @ (posedge clk);
        output wr_en,wr_data, rd_en;
        input  wr_full, rd_data,rd_empty;
    endclocking
    modport tx(clocking cb);
endinterface //FifoIf
typedef virtual FifoIf.tx vFifoIf;


class FifoDrv;
// import fifo_pkg::*;
vFifoIf m_fifo_vif;

extern function new( input vFifoIf fifo_vif );
extern function build();
extern task run();

extern task rd_fifo();
extern task wr_fifo();

endclass //FifoDrv

function FifoDrv::new( input vFifoIf fifo_vif );
    m_fifo_vif = fifo_vif;
endfunction:new
function FifoDrv::build();
endfunction:build

task FifoDrv::rd_fifo();
    int cnt = 0;
    int rddata;
    m_fifo_vif.cb.rd_en <= 1'b0;
    // repeat(20) @(m_fifo_vif.cb );
    while ( 1 ) begin
        @(m_fifo_vif.cb);
        if( !m_fifo_vif.cb.rd_empty )begin
            m_fifo_vif.cb.rd_en <= $random%2;
        end
        @(m_fifo_vif.cb);
        m_fifo_vif.cb.rd_en   <= 1'b0;
        cnt++;
    end
endtask //rd_fifo
task FifoDrv::wr_fifo();
    int cnt = 0;
    int wr_en = 0;
    m_fifo_vif.cb.wr_en <= 1'b0;
    while ( cnt<16 ) begin
        @(m_fifo_vif.cb);
        if( !m_fifo_vif.cb.wr_full )begin
            wr_en = $random%2;
            m_fifo_vif.cb.wr_en   <= wr_en;
            m_fifo_vif.cb.wr_data <= cnt+1;
            @(m_fifo_vif.cb);
            m_fifo_vif.cb.wr_en   <= 1'b0;

            if( wr_en )
                cnt++;
         end
    end
endtask //wr_fifo

task FifoDrv::run();
    top.reset();
    fork
        wr_fifo();
        rd_fifo();
    join_none

    #2000;
    $finish;
endtask //run



program automatic fifo_test( FifoIf.tx fifo_if );
FifoDrv cFifoDrv;
initial begin
    cFifoDrv = new( fifo_if );
    cFifoDrv.build();
    cFifoDrv.run();
end
endprogram:fifo_test