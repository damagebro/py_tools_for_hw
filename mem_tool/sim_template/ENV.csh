set SCP_PATH = `pwd`
setenv SIM_DIR $SCP_PATH
setenv VER_DIR $SCP_PATH/tb/
setenv TC_DIR $SCP_PATH/tc/
setenv SHELL_DIR $SIM_DIR/../shell_template/

if ( ! -d "./bin/" ) then
    mkdir ./bin/
endif

echo $SIM_DIR
echo $SHELL_DIR
