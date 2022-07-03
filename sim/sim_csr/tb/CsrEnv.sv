class ApbEnv;

// mailbox mbx_gen2drv;
// event evt_gen2drv;
vApbTbIf m_apb_vif;
ApbDrv cApbDrv;

extern function new( input vApbTbIf apb_vif );
extern function build();
extern task run();

endclass //ApbEnv

function ApbEnv::new( input vApbTbIf apb_vif );
    m_apb_vif = apb_vif;
endfunction:new
function ApbEnv::build();
    cApbDrv = new( m_apb_vif );
endfunction:build

task ApbEnv::run();
    cApbDrv.run();
endtask:run

