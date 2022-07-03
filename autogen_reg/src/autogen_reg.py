'''
usage: python ./autogen_reg.py [fn_cfg]
'''

import os,sys,re
import get_reglist
import gen_new_doc
import gen_rtl
from configparser import ConfigParser

class reg_one:
    regname = ''
    addr = 0
    attr_type = '' #cfg, cmd, status, mem, slave, pkg
    attr_spec = '' #shadow, repeat N
    attr_sw = '' #RW, RO, WO, [R|R1C][W|W1C]
    attr_hw = ''
    list_signal = [] #str_signame, str_bits_scope, default_val, str_comment

class autogen_reg():
    #variable
    reg_cfg = ConfigParser(); #reg_cfg.read(fn_cfg)
    str_docname = ''
    str_xmlname = ''
    str_outname = ''
    m_reg_bytelen = 4
    m_list_creg = []

    #class
    mc_xml_parser   = None
    mc_gen_new_doc = None
    mc_gen_rtl     = None

    def __init__(self,fn_cfg):
        self.mc_xml_parser   = get_reglist.xml_parser()
        self.mc_gen_new_doc = gen_new_doc.reg2doc()
        self.mc_gen_rtl = gen_rtl.reg2rtl()
        self.reg_cfg.read(fn_cfg)
    def check_dir_tree(self):
        work_dir = self.reg_cfg['FILE']['work_dir']
        if( not os.path.isdir(work_dir) ):
            os.makedirs(work_dir)
            # cmd = 'mkdir %s'%(work_dir); print(cmd)
            # os.system(cmd)
        astr_dir = ['rtl','doc','cpp','sv']
        for s1 in astr_dir:
            one_dir = work_dir + s1
            if( not os.path.isdir(one_dir) ):
                os.makedirs(one_dir)
                # cmd = 'cd %s && mkdir %s'%(work_dir,s1)
                # os.system(cmd)
    def create(self):
        cwd = os.getcwd()
        self.str_docname = cwd +'/'+ self.reg_cfg['FILE']['fn_indoc']
        self.str_xmlname = cwd +'/'+ self.reg_cfg['FILE']['work_dir'] + '/doc/'+ (self.reg_cfg['FILE']['top_name']+'_register.xml')
        # self.str_outname = cwd +'/'+ self.reg_cfg['FILE']['work_dir'] + '/doc/'+ (self.reg_cfg['FILE']['top_name']+'_register.docx')
        self.str_outname =           self.reg_cfg['FILE']['work_dir'] + '/doc/'+ (self.reg_cfg['FILE']['top_name']+'_register.docx')
        self.m_reg_bytelen = int(int(self.reg_cfg['ATTR']['reg_bitwidth'])/8)
        self.mc_xml_parser.m_reg_bytelen = self.m_reg_bytelen
        self.check_dir_tree()
    def run(self):
        #1. get reglist
        self.create()
        self.mc_xml_parser.doc2xml(self.str_docname,self.str_xmlname)
        self.mc_xml_parser.xml2reglist(self.str_xmlname)
        self.m_list_creg = self.mc_xml_parser.m_list_creg; #print(self.m_list_creg)
        #2. reg2doc
        self.mc_gen_new_doc.run(self.m_list_creg,self.str_outname)
        #3. reg2rtl
        self.mc_gen_rtl.run(self.m_list_creg,self.reg_cfg)


if __name__ == "__main__":
    fn_cfg = './base_reg.txt'
    if( len(sys.argv)>1 ):
        fn_cfg = sys.argv[1]

    if( not os.path.isfile(fn_cfg) ):
        print( 'error! the file %s is not exist\n'%(fn_cfg) )
        exit(-1)

    cautogen_reg = autogen_reg(fn_cfg)
    cautogen_reg.run()

    print('generate register successfully\n')
    os.system('pause')