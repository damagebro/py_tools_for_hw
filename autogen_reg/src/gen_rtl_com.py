import os,sys,re
import copy
import datetime
import gen_rtl_basestr
from configparser import ConfigParser

def clip3( a, min, max ):
    b = a
    if( a<min ):
        b = min
    elif( a>max ):
        b = max
    return b

def deal_bits_scope( str_bits_scope ):
    'ret: bw_lo, bw_hi, oneb_flag'
    str_tmp = str_bits_scope
    str_pat = '\[|\]'
    str_rep = ''
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)

    uibw_hi = int( str_tmp.split(':')[0] )
    uibw_lo = int( uibw_hi )
    oneb_flag = 1
    if( len(str_tmp.split(':')) > 1 ):
        uibw_lo = int( str_tmp.split(':')[1] )
        oneb_flag = 0

    return( uibw_lo,uibw_hi,oneb_flag )
def deal_default_val( str_default_val ):
    'func: 0xab_ca -> 0xabca -> int(0xabca,16)'
    ui_init = 0
    if( str_default_val != '' ):
        str_tmp = ''
        for s1 in str_default_val.split('_'):
            str_tmp += s1
        if( len(re.findall( '0x.*',str_tmp,flags=0)) ):
            ui_init = int(str_tmp,16)
        else:
            ui_init = int(str_tmp)
    return ui_init
def deal_list_default_val( str_default_val ):
    'func: 0xab_ca,0x1_0 -> 0xabca,0x10 -> [int(0xabca,16),int(0x10,16)]'
    ui_init = 0
    li_init = []
    if( str_default_val != '' ):
        for s_val in str_default_val.split(','):
            str_tmp = ''
            for s1 in s_val.split('_'):
                str_tmp += s1
            if( len(re.findall( '0x.*',str_tmp,flags=0)) ):
                ui_init = int(str_tmp,16)
            else:
                ui_init = int(str_tmp)
            li_init.append( ui_init )
    return li_init
def deal_str_spec( str_spec ):
    "[repeat N[, shadow]]"
    ui_rpt_num = 1
    b_shd_flag = 0
    if( str_cmpin( str_spec,"repeat") ):
        list_spec = str_spec.split(',')
        for str_one in list_spec:
            if( str_cmpin( str_one,"repeat") ):
                str_num = str_one.split()[-1]
                ui_rpt_num = int(str_num)
                break
    if( str_cmpin( str_spec,"shadow") ):
        b_shd_flag = 1

    return ui_rpt_num,b_shd_flag

def str_cmpeq( str1, str2 ):
    # return( len(re.findall(str2,str1,flags='re.I')) )
    return str1==str2
def str_cmpin( str1, str2 ):
    # return( len(re.findall(str2,str1,flags='re.I')) )
    return( len(re.findall(str2,str1,flags=0)) )

def get_basemodule_str(reg_cfg,str_module_suffix="csr_slave"):
    str_mod = ''

    str_tmp = gen_rtl_basestr.str_head
    str_pat = '<author>'
    str_rep = reg_cfg['SPEC']['author']
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)

    str_pat = '<email>'
    str_rep = reg_cfg['SPEC']['email']
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)

    str_pat = '<date>'
    str_rep = datetime.datetime.now().strftime("%Y/%m/%d-%H:%M:%S")
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)
    str_mod += str_tmp
    str_mod += '\n'*2

    str_tmp = gen_rtl_basestr.str_module
    str_pat = '<MODULE_NAME>'
    str_rep = reg_cfg['FILE']['top_name'] + '_'+str_module_suffix
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)
    str_mod += str_tmp

    # print(str_mod)
    return(str_mod)
def get_isreglist(list_creg,reg_cfg):
    uireg_bitwidth = int(reg_cfg['ATTR']['reg_bitwidth'])
    uireg_bytelen  = int(uireg_bitwidth/8)
    list_isreg = []

    for idx_creg in range(len(list_creg)):
        reg_last_flag = idx_creg == len(list_creg)-1
        one_creg = list_creg[idx_creg]
        str_type  = one_creg.attr_type
        if( str_cmpeq(str_type,'cfg') or str_cmpeq(str_type,'cmd') or str_cmpeq(str_type,'status') ):
            # isreg_one = autogen_reg.reg_one()
            # bkreg = one_creg
            isreg_one = copy.copy(one_creg)
            isreg_one.list_signal = []

            for idx_sgl in range(len(one_creg.list_signal)):
                sgl_last_flag = idx_sgl == len(one_creg.list_signal)-1
                a_sgl = one_creg.list_signal[idx_sgl];  #[str_signame, str_bits_scope, default_val, str_comment]
                uibw_lo, uibw_hi, oneb_flag = deal_bits_scope(a_sgl[1]); #print( uibw_lo, uibw_hi, oneb_flag )
                if( uibw_lo >= uireg_bitwidth ):
                    print("error!! reg_bitwidth overflow.  reg_cfg:{:d}, but typed in doc:{:d}".format(uireg_bitwidth,uibw_lo))
                    # exit(-1)
                    continue
                elif( uibw_hi > uireg_bitwidth-1 ):
                    print("warning!! reg_bitwidth overflow.  reg_cfg:{:d}, but typed in doc:{:d}".format(uireg_bitwidth,uibw_hi))
                    uibw_hi = min(uibw_hi,uireg_bitwidth-1)

                str_bw = a_sgl[1]
                if( not oneb_flag ):
                    str_bw = '[%d:%d]' % (uibw_hi,uibw_lo)
                isreg_one.list_signal.append(a_sgl)
                # print(isreg_one.list_signal[idx_sgl],'ori:',a_sgl)

            list_isreg.append(isreg_one)
    return(list_isreg)
def get_str_port(list_isreg,reg_cfg,mod_port='tx'):
    '''
    mod_port: tx/rx/con/inst
    ret:
    >>>
    *tx  : output wire [31:0] RegVarR;
    *rx  : input  wire [31:0] RegVarR;
    *con : wire [31:0] RegVarR;
    *inst: <indent>.RegVarR( RegVarR ),
    >>>
    '''
    uireg_bitwidth = int(reg_cfg['ATTR']['reg_bitwidth'])
    uireg_bytelen  = int(uireg_bitwidth/8)
    str_port = ''
    list_port = [] #['\n//RegName\n',['RegVarName','[sw_bitwidth]',i/o],..,'\n//RegName\n',...];  i/o mean for tx;

    for idx_reg in range(len(list_isreg)):
        reg_last_flag = idx_reg == len(list_isreg)-1
        one_creg = list_isreg[idx_reg]
        str_type = one_creg.attr_type
        str_reg  = one_creg.regname
        # assert( str_cmpeq(str_type,'cfg') or str_cmpeq(str_type,'cmd') or str_cmpeq(str_type,'status') )

        ui_rpt_num, b_shd_flag = deal_str_spec(one_creg.attr_spec)
        str_repeat = ''
        if( ui_rpt_num>1 ):
            str_repeat = '[%d:0]' % (ui_rpt_num-1)

        if( mod_port=='tx' ):
            list_port.append( '<indent>//%s\n'%(str_reg) )
        for idx_sgl in range(len(one_creg.list_signal)):
            sgl_last_flag = idx_sgl == len(one_creg.list_signal)-1
            a_sgl = one_creg.list_signal[idx_sgl];  #[str_signame, str_bits_scope, default_val, str_comment]
            uibw_lo, uibw_hi, oneb_flag = deal_bits_scope(a_sgl[1]); #print( uibw_lo, uibw_hi, oneb_flag )

            str_sgl = a_sgl[0]
            str_var = str_reg + '_' + str_sgl
            str_bw  = ''
            str_io  = ''
            if( str_cmpeq(str_type,'cfg') ):
                str_var1= str_var + 'R'
                if( not oneb_flag ):
                    str_bw = '[%d:%d]' % (uibw_hi-uibw_lo,0)
                str_io  = 'o'
            elif( str_cmpeq(str_type,'cmd') ):
                str_var1= str_var + 'OEn'
                str_bw  = ''
                str_io  = 'o'
                list_port.append([str_var1,str_repeat+str_bw,str_io])

                str_var1= str_var + 'O'
                if( not oneb_flag ):
                    str_bw = '[%d:%d]' % (uibw_hi-uibw_lo,0)
                str_io  = 'o'
            elif( str_cmpeq(str_type,'status') ):
                if( str_cmpin(one_creg.attr_sw,'W') ):
                    str_var1= str_var + 'OEn'
                    str_bw  = ''
                    str_io  = 'o'
                    list_port.append([str_var1,str_repeat+str_bw,str_io])

                    str_var1= str_var + 'O'
                    if( not oneb_flag ):
                        str_bw = '[%d:%d]' % (uibw_hi-uibw_lo,0)
                    str_io  = 'o'
                    if( str_cmpeq(one_creg.attr_sw,'RW') ):
                        list_port.append([str_var1,str_repeat+str_bw,str_io])
                if( str_cmpin(one_creg.attr_sw,'R') ):
                    str_var1= str_var + 'D'
                    if( not oneb_flag ):
                        str_bw = '[%d:%d]' % (uibw_hi-uibw_lo,0)
                    str_io  = 'i'
            list_port.append([str_var1,str_repeat+str_bw,str_io])
        #end of for idx_sgl
        # print(list_port)
    #end of for idx_reg

    for idx_obj in range(len(list_port)):
        obj_last_flag = idx_obj == len(list_port)-1
        obj = list_port[idx_obj]
        if( type(obj) == str ):
            str_port += obj
        else:
            str_var= obj[0]
            str_bw = obj[1]
            str_io = obj[2]
            str_put = ''
            str_line= ''
            str_comma = ',\n'
            if( obj_last_flag ):
                str_comma = '//,'
            if( mod_port=='tx' ):
                if( str_io=='i' ):
                    str_put = 'input'
                elif( str_io=='o' ):
                    str_put = 'output'
                str_line= '{:6s} wire {:20s}{:30s}{}'.format(str_put,str_bw,str_var,str_comma)
            elif( mod_port=='rx' ):
                if( str_io=='o' ):
                    str_put = 'input'
                elif( str_io=='i' ):
                    str_put = 'output'
                str_line= '{:6s} wire {:20s}{:30s}{}'.format(str_put,str_bw,str_var,str_comma)
            elif( mod_port=='con' ):
                str_line= 'wire {:10s} {:30s};\n'.format(str_bw,str_var)
            elif( mod_port=='inst' ):
                str_line= "<indent>.{:30s}( {:30s} ){}".format(str_var,str_var,str_comma)

            str_port += str_line
        #end of else
    #end of for idx_reg
    # print(str_port)
    return(str_port)

def check_cfg_shadow(list_creg):
    '''
    func: check is it 'type:cfg, spec:shadow' here;
    ret: b_shadow_reg_flag;
    '''
    b_shadow_reg_flag = 0
    for one_creg in list_creg:
        str_type = one_creg.attr_type
        str_spec = one_creg.attr_spec
        if( str_cmpeq(str_type,'cfg') and str_cmpin(str_spec,'shadow') ):
            b_shadow_reg_flag = 1
            break
    return b_shadow_reg_flag