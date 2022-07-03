

import os,sys,re
from win32com import client as wc
import xml.etree.ElementTree as ET
from autogen_reg import reg_one

def str_cmpin( str1, str2 ):
    # return( len(re.findall(str2,str1,flags='re.I')) )
    return( len(re.findall(str2,str1,flags=0)) )
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

def str_undecorate(str_underline):
    "func: 0x12_34 -> 0x1234"
    astr1 = str_underline.split('_'); print(astr1)
    str_tmp = ''
    for s in astr1:
        str_tmp += s
    print(str_tmp)

    return str_tmp

class xml_parser():
    m_reg_bytelen = 4
    m_list_creg = []

    def __init__(self):
        pass

    def doc2xml(self,str_docname,str_xmlname):
        word = wc.Dispatch('Word.Application')
        # str_docname = r'C:\Users\tangyin\personal\proj\autogen_reg\py_scp/../doc/寄存器配置.docx'
        # str_xmlname = r'C:\Users\tangyin\personal\proj\autogen_reg\py_scp/../bin/寄存器配置.xml'

        if( not os.path.isfile( str_docname ) ):
            print( 'error! the file "%s" is not exist\n'%(str_docname) )
            exit(-1)
        doc = word.Documents.Open(str_docname)
        doc.SaveAs(str_xmlname , 11) #17对应于下表中的pdf文件
        doc.Close()
        # word.Quit()

    def xml2reglist(self, str_xmlname):
        tree = ET.parse(str_xmlname)
        root = tree.getroot()

        ns = {'w': 'http://schemas.microsoft.com/office/word/2003/wordml',
             'wx': 'http://schemas.microsoft.com/office/word/2003/auxHint'}

        elm_reg = self.get_target_elmemt(root,ns)
        list_tbl= self.get_table(elm_reg,ns)
        self.get_all_reg(list_tbl)
    def get_target_elmemt(self, elm_root, ns):
        'return elm_寄存器定义'
        pat_flag = 0
        elm_pat  = 0
        str_tmp    = ''
        for elm_subsect in elm_root.findall('.//wx:sub-section', ns):
            #print(elm_subsect.tag,'|-->',elm_subsect.text)
            if( pat_flag ):
                break
            for elm_p in elm_subsect.findall( './w:p',ns ):
                if( pat_flag ):
                    break
                for elm_t in elm_p.findall( './w:r/w:t',ns ):
                    str_tmp += elm_t.text
                print(elm_t.tag,'|-->',str_tmp)
                pat = re.findall('.*寄存器定义',str_tmp)
                if( len(pat) ):
                    pat_flag = 1
                    elm_pat = elm_subsect
                    break

        print(elm_pat.tag,'|-->',elm_pat.text)
        return(elm_pat)
    def get_table(self, elm_target, ns):
        'func: xml to list_table'
        elm_reg = elm_target
        #print(elm_reg.tag,'|-->',elm_reg.text)
        str_tmp = ''
        list_tbl = list() #[tbl][tr]
        tr = 0
        tbl= 0
        for elm_sub in elm_reg.findall('.//wx:sub-section', ns):
            for elm_tbl in elm_sub.findall('./w:tbl', ns):
                tr = 0
                list_tbl.append([])
                for elm_tr in elm_tbl.findall('.//w:tr', ns):
                    tc = 0
                    list_tbl[tbl].append([])
                    for elm_tc in elm_tr.findall('.//w:tc', ns):
                        str_tmp = ''
                        for elm_p in elm_tc.findall( './w:p',ns ):
                            for elm_t in elm_p.findall( './w:r/w:t',ns ):
                                str_tmp += elm_t.text
                            if( tr>=4 and tc==3 ):
                                str_tmp += '\n'

                        list_tbl[tbl][tr].append(str_tmp)
                        tc += 1
                    tr += 1
                tbl += 1

        return list_tbl
    def get_all_reg( self, list_tbl ):
        '''
        func: list_table to list_cls_table
        ['寄存器名', 'CFG_REG', 'offset', '0x10']
        ['type', 'cfg', 'spec.', '-']
        ['SW', 'RW', 'HW', 'RW']
        ['信号名', '位段定义', 'default', 'comment']
        ['var_name1', '[0]', '0x1', '']
        ['var_name2', '[7:4]', '0x1_0', '图像高']
        '''
        idx_tbl = 0
        uiaddr_tmp = 0
        for tbl in list_tbl:
            print("--------------- tbl ---------------------",idx_tbl)
            creg_one = reg_one()
            creg_one.list_signal = []
            # for row in tbl:
            #     print(row)
            creg_one.regname = tbl[0][1]; #print(creg_one.regname)
            if( tbl[0][3] != '' ):
                if( len(re.findall( '0x.*',tbl[0][3],flags=0)) ):
                    uiaddr_tmp = int(tbl[0][3],16)
                else:
                    uiaddr_tmp = int(tbl[0][3])
            # creg_one.addr    = hex(uiaddr_tmp); #print(creg_one.addr)
            creg_one.addr    = uiaddr_tmp; #print(creg_one.addr)

            creg_one.attr_type = tbl[1][1]
            creg_one.attr_spec = tbl[1][3]
            creg_one.attr_sw   = tbl[2][1]
            creg_one.attr_hw   = tbl[2][3]

            for i in range( 4, len(tbl) ):
                #['信号名', '位段定义', 'default', 'comment']
                if( tbl[i][2]=='' ):
                    tbl[i][2] = '0x0'
                creg_one.list_signal.append(tbl[i])
            self.m_list_creg.append(creg_one); #print(creg_one.list_signal)


            idx_tbl += 1
            ui_rpt_num, b_shd_flag = deal_str_spec(creg_one.attr_spec)
            uiaddr_tmp += (self.m_reg_bytelen)*ui_rpt_num

        #same regname check
        for i in range(idx_tbl):
            b_same_flag = 0
            same_cnt = 1
            str_regname_i = self.m_list_creg[i].regname
            for j in range(i+1,idx_tbl):
                str_regname_j = self.m_list_creg[j].regname
                if( str_regname_i==str_regname_j ):
                    b_same_flag = 1
                    same_cnt += 1
                    str_regname_new = str_regname_i + '{:d}'.format(same_cnt)
                    self.m_list_creg[j].regname = str_regname_new
            if( b_same_flag ):
                str_regname_new = str_regname_i + '{:d}'.format(1)
                self.m_list_creg[i].regname = str_regname_new
