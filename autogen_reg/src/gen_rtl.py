import os,sys,re
import datetime
import copy
from gen_rtl_slv import gen_rtl_slv
from gen_rtl_slvreg import gen_rtl_slvreg
from gen_rtl_tmp_inst import gen_rtl_tmp_inst
import gen_rtl_check
from configparser import ConfigParser

class reg2rtl():
    def __init__(self):
        pass
    def run(self,list_creg,reg_cfg):
        gen_rtl_check.check_all( list_creg,reg_cfg )
        uireg_count = gen_rtl_slv(list_creg,reg_cfg)
        if( uireg_count ):
            gen_rtl_slvreg(list_creg,reg_cfg)
            gen_rtl_tmp_inst(list_creg,reg_cfg)

if __name__ == "__main__":
    # fn_cfg  = './reg.cfg'
    # reg_cfg = ConfigParser(); reg_cfg.read(fn_cfg)
    # gen_csr_slv(list_creg,reg_cfg)
    # gen_csr_slvreg(list_creg,reg_cfg)

    pass