SCP_PATH=`pwd`
export SIM_DIR=$SCP_PATH
export VER_DIR=$SCP_PATH/tb/
export TC_DIR=$SCP_PATH/tc/
export SHELL_DIR=$SIM_DIR/../shell_template/

if [ ! -d "./bin/" ]
then
    mkdir ./bin/
fi

echo ${SIM_DIR}