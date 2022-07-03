class ApbDrv;

// import apb_pkg::*;
vApbTbIf m_apb_vif;

extern function new( input vApbTbIf apb_vif );
extern function build();
extern task run();

extern task apb_write( int addr, int data );
extern task apb_read( int addr, ref int rd_data );
extern task stim_apb();

endclass //ApbDrv

function ApbDrv::new( input vApbTbIf apb_vif );
    m_apb_vif = apb_vif;
endfunction:new
function ApbDrv::build();
endfunction:build

task ApbDrv::apb_write( int addr, int data );
    @(m_apb_vif.cb);
    m_apb_vif.cb.psel    <= 1'b1;
    m_apb_vif.cb.penable <= 1'b0;
    m_apb_vif.cb.pwrite  <= 1'b1;
    m_apb_vif.cb.paddr   <= addr;
    @(m_apb_vif.cb);
    m_apb_vif.cb.penable <= 1'b1;
    m_apb_vif.cb.pwdata  <= data;
    do
        @(m_apb_vif.cb);
    while( m_apb_vif.cb.pready==1'b0 );
    m_apb_vif.cb.psel    <= 1'b0;
    m_apb_vif.cb.penable <= 1'b0;
    @(m_apb_vif.cb);
endtask //apb_write

task ApbDrv::apb_read( int addr, ref int rd_data );
    @(m_apb_vif.cb);
    m_apb_vif.cb.psel    <= 1'b1;
    m_apb_vif.cb.penable <= 1'b0;
    m_apb_vif.cb.pwrite  <= 1'b0;
    m_apb_vif.cb.paddr   <= addr;
    @(m_apb_vif.cb);
    m_apb_vif.cb.penable <= 1'b1;
    do
        @(m_apb_vif.cb);
    while( m_apb_vif.cb.pready==1'b0 );
    m_apb_vif.cb.psel    <= 1'b0;
    m_apb_vif.cb.penable <= 1'b0;
    rd_data = m_apb_vif.cb.prdata;
    // @(m_apb_vif.cb);
endtask //apb_read

task ApbDrv::stim_apb();
    int rd_data;
    for( int i=0; i<4; i++ )begin
        apb_write( 32'h100+i*4, 32'h010+i*8 );
    end

    // top.reset();
    top.xclear();
    #100;
    for( int i=0; i<20; i++ )begin
        apb_write( 32'h100+i*4, $random() );
    end

    apb_write( 'h200, 1 );
    apb_read( 'h000, rd_data );
    apb_read( 'h100, rd_data );
    apb_read( 'h110, rd_data );
    apb_read( 'h400, rd_data );
endtask //stim_one_frame

task ApbDrv::run();
    top.reset();
    #100;
    fork
        stim_apb();
        #100us;
    join_any
    #100;
    $finish;
endtask //run