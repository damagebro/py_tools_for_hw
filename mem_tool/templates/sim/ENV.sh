SCP_PATH=`pwd`
export SIM_DIR=$SCP_PATH

if [ ! -d "./bin/" ]
then
    mkdir ./bin/
fi

echo "SIM_DIR=$SIM_DIR"
