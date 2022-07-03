SCP_PATH=`pwd`
export SIM_DIR=$SCP_PATH
export RTL_DIR=$SCP_PATH/../../rtl/
export VER_DIR=$SCP_PATH/tb/
export TC_DIR=$SCP_PATH/tc/

export RTL_PATH=$RTL_DIR/

if [ ! -d "./bin/" ]
then
    mkdir ./bin/
fi

echo ${RTL_DIR}