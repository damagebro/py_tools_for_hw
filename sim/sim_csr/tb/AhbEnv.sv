class AhbEnv;

// mailbox mbx_gen2drv;
// event evt_gen2drv;
vAhbTbIf m_ahb_vif;
AhbDrv cAhbDrv;

extern function new( input vAhbTbIf ahb_vif );
extern function build();
extern task run();

endclass //AhbEnv

function AhbEnv::new( input vAhbTbIf ahb_vif );
    m_ahb_vif = ahb_vif;
endfunction:new
function AhbEnv::build();
    cAhbDrv = new( m_ahb_vif );
endfunction:build

task AhbEnv::run();
    cAhbDrv.run();
endtask:run

