class AhbDrv;

// import ahb_pkg::*;
vAhbTbIf m_ahb_vif;

extern function new( input vAhbTbIf ahb_vif );
extern function build();
extern task run();

extern task ahb_single_write( int addr, int data );
extern task ahb_single_read( int addr, ref int rd_data );
extern task stim_ahb();

endclass //AhbDrv

function AhbDrv::new( input vAhbTbIf ahb_vif );
    m_ahb_vif = ahb_vif;
endfunction:new
function AhbDrv::build();
endfunction:build

task AhbDrv::ahb_single_write( int addr, int data );
    m_ahb_vif.cb.hready   <= 1'b1;
    m_ahb_vif.cb.htrans   <= 3'd2; //0:idle, 1:busy, 2:nonseq, 3:seq
    m_ahb_vif.cb.hsize    <= 3'd2;
    m_ahb_vif.cb.hburst   <= 'b0; //0:single, 1:incr
    m_ahb_vif.cb.hprot    <= 'b0; //tie 4'b0

    @(m_ahb_vif.cb);
    m_ahb_vif.cb.hselx   <= 1'b1;
    m_ahb_vif.cb.hwrite  <= 1'b1;
    m_ahb_vif.cb.haddr   <= addr;
    @(m_ahb_vif.cb);
    m_ahb_vif.cb.haddr   <= 0;
    m_ahb_vif.cb.hwdata  <= data;
    do
        @(m_ahb_vif.cb);
    while( m_ahb_vif.cb.hready_out==1'b0 );
    m_ahb_vif.cb.hselx    <= 1'b0;
endtask:ahb_single_write

task AhbDrv::ahb_single_read( int addr, ref int rd_data );
    m_ahb_vif.cb.hready   <= 1'b1;
    m_ahb_vif.cb.htrans   <= 3'd2; //0:idle, 1:busy, 2:nonseq, 3:seq
    m_ahb_vif.cb.hsize    <= 3'd2;
    m_ahb_vif.cb.hburst   <= 'b0; //0:single, 1:incr
    m_ahb_vif.cb.hprot    <= 'b0; //tie 4'b0

    @(m_ahb_vif.cb);
    m_ahb_vif.cb.hselx   <= 1'b1;
    m_ahb_vif.cb.hwrite  <= 1'b0;
    m_ahb_vif.cb.haddr   <= addr;
    @(m_ahb_vif.cb);
    do
        @(m_ahb_vif.cb);
    while( m_ahb_vif.cb.hready_out==1'b0 );
    m_ahb_vif.cb.hselx    <= 1'b0;
    rd_data = m_ahb_vif.cb.hrdata;
endtask:ahb_single_read

task AhbDrv::stim_ahb();
    int rd_data;
    for( int i=0; i<4; i++ )begin
        ahb_single_write( 32'h100+i*4, 32'h010+i*8 );
    end

    // top.reset();
    top.xclear();
    #100;
    for( int i=0; i<20; i++ )begin
        ahb_single_write( 32'h100+i*4, $random() );
    end

    ahb_single_write( 'h200, 1 );
    ahb_single_read( 'h000, rd_data );
    ahb_single_read( 'h100, rd_data );
    ahb_single_read( 'h110, rd_data );
    ahb_single_read( 'h400, rd_data );
endtask //stim_one_frame

task AhbDrv::run();
    top.reset();
    #100;
    fork
        stim_ahb();
        #100us;
    join_any
    #100;
    $finish;
endtask //run