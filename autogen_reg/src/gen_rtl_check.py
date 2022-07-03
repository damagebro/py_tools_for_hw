import os,sys,re
from gen_rtl_com import*

def pause_diy():
    os.system("pause")
def exit_diy():
    pause_diy()
    exit(-1)
def print_diy( s ):
    print( "NOTICE(), {:s}".format(s) )
def print_reg( idx, reg_one ):
    print_diy( "寄存器表格填写出错， 出错位置:%d"%(idx) )
    err_str = "---------------the register information is:------------------\n"
    err_str+= "regname:{:20s}, offset:{:d}\n".format( reg_one.regname, reg_one.addr )
    err_str+= "type:{:10s}, spec:{:s}\n".format( reg_one.attr_type, reg_one.attr_spec )
    err_str+= "SW  :{:10s}, HW  :{:s}\n".format( reg_one.attr_sw, reg_one.attr_hw )
    for li in reg_one.list_signal:
        err_str+= "signal_name:{:s}, bits_scope:{:s}, default:{:s}\n".format( li[0], li[1], li[2] )
    print_diy( err_str )

def check_acc(list_creg, reg_cfg):
    'func: check "offset", "signal bits_scrope [10:0]" accumulation error'
    uireg_bitwidth = int(reg_cfg['ATTR']['reg_bitwidth'])
    uireg_bytelen = uireg_bitwidth/8
    pre_addr = -1
    for idx in range( len(list_creg) ):
        one = list_creg[idx]
        cur_addr = one.addr
        addr_acc_right_cond = (cur_addr>=pre_addr+uireg_bytelen) or pre_addr==-1
        pre_addr = cur_addr

        signal_acc_right_cond = True
        pre_bw_hi = -1
        for li in one.list_signal:
            bw_lo, bw_hi, oneb_flag = deal_bits_scope( li[1] )
            signal_acc_right_cond = bw_lo>pre_bw_hi
            if( not signal_acc_right_cond ):
                break
            pre_bw_hi = bw_hi
        if( not addr_acc_right_cond or not signal_acc_right_cond ):
            print_diy( "地址递增，或信号比特位递增错误" )
            print_reg( idx, one )
            exit_diy()

def check_name( list_creg,reg_cfg ):
    'func: check "reg_name", "signal_name" types error'
    for idx in range( len(list_creg) ):
        one = list_creg[idx]
        regname = one.regname
        regname_right_cond = 1
        for s in regname.split("_"):
            if( not s.isalnum() ):
                regname_right_cond = 0
        signal_right_cond = 1
        for li in one.list_signal:
            signal_name = li[0]
            for s in signal_name.split("_"):
                if( not s.isalnum() ):
                    signal_right_cond = 0
            if( not signal_right_cond ):
                break
        if( not regname_right_cond or not signal_right_cond ):
            print_diy( "寄存器名，或信号名填写错误" )
            print_reg( idx, one )
            exit_diy()
def check_attr( list_creg,reg_cfg ):
    'func: check "type", "sw/hw" types error'
    for idx in range( len(list_creg) ):
        one = list_creg[idx]
        type = one.attr_type
        spec = one.attr_spec
        sw = one.attr_sw
        hw = one.attr_hw
        #check type
        li_type = ["cfg","status","cmd","slave","mem","pkg"]
        type_right_cond = 0
        for s in li_type:
            if( type==s ):
                type_right_cond=1
        #check sw/hw
        sw_right_cond = 0
        hw_right_cond = 0
        li_sw_hw = ["WO","RO","RW","R1C","W1C"]
        for s in li_sw_hw:
            if( sw==s ):
                sw_right_cond = 1
            if( hw==s ):
                hw_right_cond = 1
        if( type=="slave" or type=="mem" or type=="pkg" ):
            sw_right_cond = 1
            hw_right_cond = 1
        #check type+sw/hw
        type_constraint_right_cond = 0
        if( type=="cfg" and (sw=="RW" and hw=="RO") ):
            type_constraint_right_cond = 1
        if( type=="status" and ((sw=="RO" and hw=="WO") or (sw=="RW" and hw=="RW") or (sw=="WO" and hw=="RO")) ):
            type_constraint_right_cond = 1
        if( type=="cmd" and (sw=="WO" and hw=="RO") ):
            type_constraint_right_cond = 1
        if( type=="slave" or type=="mem" or type=="pkg" ):
            type_constraint_right_cond = 1

        if( not type_right_cond or not sw_right_cond or not hw_right_cond or not type_constraint_right_cond ):
            print_diy( "寄存器属性填写错误" )
            print_reg( idx, one )
            exit_diy()


def check_all( list_creg,reg_cfg ):
    check_name( list_creg, reg_cfg )
    check_attr( list_creg, reg_cfg )
    check_acc( list_creg, reg_cfg )


# class reg_one:
#     regname = ''
#     addr = 0
#     attr_type = '' #cfg, cmd, status, mem, slave, pkg
#     attr_spec = '' #shadow, repeat N
#     attr_sw = '' #RW, RO, WO, [R|R1C][W|W1C]
#     attr_hw = ''
#     list_signal = [] #str_signame, str_bits_scope, default_val, str_comment