import os,sys,re
from gen_rtl_com import*
from configparser import ConfigParser

def gen_rtl_tmp_inst(list_creg, reg_cfg):
    list_isreg = get_isreglist(list_creg,reg_cfg)

    str_wr = ''
    str_wr+= '//IP core input begin----------------------------------------------------\n'
    str1 = get_str_port(list_isreg,reg_cfg,mod_port='rx')
    str_pat = '<indent>'
    str_rep = ' '*0
    str1 = re.sub(str_pat, str_rep, str1, count=0, flags=0); #print(str1)
    str_wr+= str1 + '\n'
    str_wr+= '//IP core input end  ----------------------------------------------------\n'
    str_wr+= '\n'*3

    str_wr+= '//config signal delcare begin--------------------------------------------\n'
    str1 = get_str_port(list_isreg,reg_cfg,mod_port='con')
    str_pat = '<indent>'
    str_rep = ' '*0
    str1 = re.sub(str_pat, str_rep, str1, count=0, flags=0); #print(str1)
    str_wr+= str1
    str_wr+= '//config signal delcare end  --------------------------------------------\n'
    str_wr+= '\n'*3

    str_wr+= '//config signal instance begin-------------------------------------------\n'
    str1 = get_str_port(list_isreg,reg_cfg,mod_port='inst')
    str_pat = '<indent>'
    str_rep = ' '*0
    str1 = re.sub(str_pat, str_rep, str1, count=0, flags=0); #print(str1)
    str_wr+= str1 + '\n'
    str_wr+= '//config signal instance end  -------------------------------------------\n'
    str_wr+= '\n'*3

    rtldir   = reg_cfg['FILE']['work_dir'] + '/rtl/'
    str_mod  = reg_cfg['FILE']['top_name'] + '_'+'tmp_inst'
    filepath = rtldir
    filename = filepath + '/%s.sv'%(str_mod)
    if( not os.path.isdir(filepath) ):
        os.makedirs(filepath)
        # cmd = 'cd %s && mkdir %s'%(rtldir,str_mod)
        # os.system(cmd)
    fp = open(filename,'wt')
    fp.write(str_wr)
    fp.close()