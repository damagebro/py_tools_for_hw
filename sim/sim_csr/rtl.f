//--------------------------------------
//define
//--------------------------------------
$RTL_DIR/impl_template/impl_define_sim.sv
$RTL_DIR/common/com_define.sv

//--------------------------------------
//impl
//--------------------------------------
$RTL_DIR/impl_template/com_cdc_sig.sv

//--------------------------------------
//com
//--------------------------------------
-f $RTL_DIR/csr_test.f

//--------------------------------------
//project
//--------------------------------------
${SIM_DIR}/csr_example/cu_csr_slave/cu_csr_slave.sv
${SIM_DIR}/csr_example/cu_csr_slave/cu_csr_slave_reg.sv
${SIM_DIR}/csr_example/ip_apb_top.sv
${SIM_DIR}/csr_example/ip_ahb_top.sv
