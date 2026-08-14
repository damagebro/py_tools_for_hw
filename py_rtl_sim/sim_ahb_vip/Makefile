TC ?= ahb_vip
AHB_CFG ?= ${SIM_DIR}/ahb_vip.cfg

ENV_TC_DIR = ${SIM_DIR}/tc/
RTL_F = ${SIM_DIR}/rtl.f
ENV_F = ${SIM_DIR}/testbench.f
TEMP_DIR = ${SIM_DIR}/bin/
SIM_RUN_OPT = +AHB_CFG=$(AHB_CFG)

help:
	@echo "source ENV.sh before make"
	@echo "make clean"
	@echo "make com"
	@echo "make run"
	@echo "make verdi"
	@echo "make vlt       # compile and run with Verilator"
	@echo "make vlt_com   # compile with Verilator"
	@echo "make vlt_run   # run Verilator binary"
	@echo "make vlt_wave  # open with WSL GTKWave"
	@echo "make vlt_gtk_wave"
	@echo "make run AHB_CFG=${AHB_CFG}"
	@echo "#cdns#################"
	@echo "make sim"
	@echo "make cdns_com"

clean:
	mkdir -p $(TEMP_DIR)
	rm -rf $(TEMP_DIR)*

#snps####################################################################################
SNPS_DEF = +define+DUMP_FSDB
SNPS_LINT_OPT = +lint=TFIPC-L,PCWM,CAWM,CDUB
COM_OPT = -l $(TEMP_DIR)compile.log -Mdir=$(TEMP_DIR)csrc -full64 -sverilog \
          -timescale=1ns/100ps \
          -LDFLAGS -Wl,--no-as-needed -kdb -lca -debug_access+all+reverse \
          -work mylib -o $(TEMP_DIR)simv $(SNPS_DEF) $(SNPS_LINT_OPT)
RUN_OPT = +vcs+initreg+0 +vcs+initmem+0 -l ./run.log $(SNPS_DEF) $(SIM_RUN_OPT)

com:
	mkdir -p $(TEMP_DIR)
	vcs $(COM_OPT) -top top -f $(RTL_F) -f $(ENV_F) -assert svaext

run:
	cd $(TEMP_DIR); ./simv $(RUN_OPT) +TC_DIR=${ENV_TC_DIR} +TC_NAME=${TC}

all: clean com run

verdi:
	cd $(TEMP_DIR); verdi -top top -f $(RTL_F) -f $(ENV_F) -ssf run.fsdb -sverilog -2009 -full64 &

#cdns####################################################################################
CDNS_DEF = +define+ADD_REPORT
CDNS_OPT = -64bit -sv -access rwc -timescale 1ns/100ps -vlog_ext +.h $(CDNS_DEF) \
           -loadpli1 debpli:novas_pli_boot -xmlibdirname ./xcelium.d -l ./xrun.log

sim:
	mkdir -p $(TEMP_DIR)
	cd $(TEMP_DIR); xrun $(CDNS_OPT) -top top -f $(RTL_F) -f $(ENV_F) $(SIM_RUN_OPT) -gui &

cdns_com:
	mkdir -p $(TEMP_DIR)
	cd $(TEMP_DIR); xrun $(CDNS_OPT) -elaborate -top top -f $(RTL_F) -f $(ENV_F)

#vlt#####################################################################################
VLT_F = $(TEMP_DIR)filelist.f
VLT_SIMV = $(TEMP_DIR)obj_dir/simv_$(TC)
VLT_FST = $(TEMP_DIR)run.fst
VLT_OPT = --binary --timing --assert --trace-fst --trace-structs -Wno-fatal -Wno-INITIALDLY \
-Wno-TIMESCALEMOD -Wno-WIDTHEXPAND \
-DDUMP_FST --top-module top --Mdir $(TEMP_DIR)obj_dir -o simv_$(TC)

vlt_f:
	mkdir -p $(TEMP_DIR)
	sed -e "s|\$${SIM_DIR}|$$SIM_DIR|g" rtl.f testbench.f > $(VLT_F)

vlt_com: vlt_f
	verilator $(VLT_OPT) -f $(VLT_F) > $(TEMP_DIR)compile.log 2>&1; \
		status=$$?; \
		cat $(TEMP_DIR)compile.log; \
		exit $$status

vlt_run:
	test -x $(VLT_SIMV)
	cd $(TEMP_DIR); ./obj_dir/simv_$(TC) $(SIM_RUN_OPT) > ./run.log 2>&1; \
		status=$$?; cat ./run.log; exit $$status

vlt: vlt_com vlt_run

vlt_wave: vlt_gtk_wave

vlt_gtk_wave:
	test -f $(VLT_FST)
	gtkwave $(VLT_FST) -a $(SIM_DIR)/ahb_vip.gtkw > $(TEMP_DIR)gtkwave.log 2>&1 &
