export TC=vadd_oneblk
export ENV_TC_DIR=${SIM_DIR}/../tc/
export ENV_DUMP_DIR=./dump/

RTL_F = ${SIM_DIR}/rtl.f
ENV_F = ${SIM_DIR}/testbench.f

#snps####################################################################################
# vcs -full64 -sverilog -debug_all -lca -kdb -timescale=1ns/1ps -f rtl.f -f testbench.f -top top
SNPS_DEF = +define+DUMP_FSDB

COM_OPT = -l ./compile.log  -Mdir=./csrc \
-full64 \
-sverilog \
-timescale=1ns/100ps \
-LDFLAGS -Wl,--no-as-needed \
-kdb 	\
-lca 	\
-debug_access+all+reverse \
-work mylib	\
-o	simv	\
$(SNPS_DEF)

RUN_OPT = \
+vcs+initreg+0	\
+vcs+initmem+0	\
-l ./run.log \
$(SNPS_DEF)

#snps target####################################################################################
help:
	@echo "make clean "
	@echo "make com "
	@echo "make run "
	@echo "make verdi "
	@echo "make run TC=${TC} "
	@echo "#cdns#################"
	@echo "make sim"
	@echo "make cdns_com"

clean:
	rm ./bin/ -rf; source ./ENV.sh

rtl:
	cd ./bin/; vcs  $(COM_OPT)	-f $(RTL_F)
com:
	cd ./bin/; vcs  $(COM_OPT)	-top top -f $(RTL_F) -f $(ENV_F) -assert svaext

run:
	cd ./bin/; ./simv $(RUN_OPT) +TC_DIR=${ENV_TC_DIR} +TC_NAME=${TC}

all: clean com run

verdi:
	cd ./bin/; verdi -top top -f $(RTL_F) -f $(ENV_F) -ssf run.fsdb -sswr ${SIM_DIR}/wave/signal.rc -sverilog -full64 &

#cdns####################################################################################
CDNS_DEF = +define+ADD_REPORT
CDNS_OPT = -64bit -sv -access rwc -timescale 1ns/100ps -vlog_ext +.h $(CDNS_DEF) -loadpli1 debpli:novas_pli_boot

#cdns target####################################################################################
sim:
	cd ./bin; xrun $(CDNS_OPT) -top top -f $(RTL_F) -f $(ENV_F) -gui &

cdns_com:
	cd ./bin; xrun $(CDNS_OPT) -elaborate -top top -f $(RTL_F) -f $(ENV_F)