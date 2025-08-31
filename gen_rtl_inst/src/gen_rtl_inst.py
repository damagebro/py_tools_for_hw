# -*- coding: utf-8 -*-
'''
usage: python gen_rtl_inst.py <fn_rtl>
func: gen rtl instance
input: <RTL_FILE>.v
output: inst.v with module instance
'''

import os,sys,re
from deal_str_common import*

#string condition test----------------------------------------------------
def is_null_str( s ):
    size = len( s.split() )
    return size==0 #以空白符 作为分隔符， 若字符串全是空白符， 分割后数组大小为0

#deal comment-------------------------------------------------------------
def del_wordline_cmt( li_str ):
    'func: delete <anychar>//comment, if <anychar> not null or whitespace, delete the comment after //'
    comment_mark = '//'
    li_ret = []
    for s in li_str:
        if( str_find( comment_mark )>0 ):
            li = s.split( comment_mark,1 )
            if( len(li[0].spilt()) ):  #注释前 存在非空白字符， 则删除 行注释
                li_ret.append( li[0] )
            else:
                li_ret.append( s )  #注释前 为空白字符， 保留行注释
        else:
            li_ret.append( s )
    return li_ret

def del_line_cmt( li_str ):
    comment_mark = '//'
    li_ret = []
    for s in li_str:
        li_ret.append( s.split( comment_mark,1 )[0] )
    return li_ret
def del_blk_cmt( li_str ):
    li_tmp = str_couple_split( li_str, '/*','*/' )
    li_ret = []
    li_ret.extend( li_tmp[0] )
    li_ret.extend( li_tmp[-1] )

    return li_ret
def del_all_cmt( li_str ):
    li_ret = del_line_cmt( li_str ) # 行注释 比块注释 优先级更高
    li_ret = del_blk_cmt( li_ret )

    return li_ret

#get paramter+port list-------------------------------------------------------------
def deal_port_name( s ):
    str_ret = s
    if( str_find(s,'[') ):
        str_ret = s.split('[',1)[0]
    return str_ret
def parse_port_def( s ):
    'ret: str_bit_width, str_io_direction'
    str_bit_width = ''
    if( str_find(s, '[') ):
        str_couple_split_verbose_once
        str_l = '['
        str_r = ']'
        li_tmp, li_match = str_couple_split_verbose_once( [s], str_l,str_r,1 )
        s1 = ''
        for li in li_match:
            s1+= '{}{}{}'.format( str_l, list2str(li), str_r ); #print(s1)
        str_bit_width = s1

    str_io_direction = '??'
    if( str_find(s,'input') ):
        str_io_direction = 'i'
    elif( str_find(s,'output') ):
        str_io_direction = 'o'
    elif( str_find(s,'inout') ):
        str_io_direction = 'io'
    # elif( str_re_find(s,'\w+\.\w+(?:.|\n)*') ):
    #     str_io_direction = 'if'

    return str_io_direction, str_bit_width
def get_parm_list( li_str_module ):  #[parm_name, default_value, b_independent_flag]
    '''
    * pat1: #( parameter AW=16, DW=32 )
    * pat2: paramter AW=16, DW=32;
    * pat3: paramter AW=16, DW=32, SW=DW/8;
    * pat4: paramter AW='h0__0_10, DW=32'h20;
    * pat5: paramter AW=16, paramter DW=32;
    * ret: list_parm = [param_name, default_val, b_independent_flag]
    '''
    li_parm = [] #[(str_param_name, str_default_val, b_independent_flag), ...]
    li_str_module1 = del_all_cmt( li_str_module ); #print( list2str(li_str_module1) )

    str_l = 'module'
    str_r = ';'
    b_couple_nested_flag = 0
    li_tmp = str_couple_split( li_str_module1, str_l,str_r,b_couple_nested_flag )
    li_rem = li_tmp[2]
    li_module_declare = li_tmp[1]

    #step1 get param list----
    li_parm_declare   = [] #  module #( parm_decalre_list ) inst_module ( port_declare_list );
    li_parm_statement = [] #  outside module declare,  parameter ??;
    li_parm_raw = []  # [ '?? parm_name1 = value',  '?? parm_name2 = value', ... ]

    ##get li_parm_declare
    str_l = '('
    str_r = ')'
    b_couple_nested_flag = 1
    li_tmp, li_match = str_couple_split_verbose_once( li_module_declare, str_l,str_r,b_couple_nested_flag )
    if( len( li_match )>1 ):  #module声明中， 当出现两次()被匹配上，则第一次()匹配内容是参数列表，第二次()匹配内容是信号列表
        str_parm = list2str(li_match[0]); #print( str_parm )
        li_parm_declare.extend( str_parm.split(',') )
        li_parm_raw.extend( li_parm_declare )
    ##get li_parm_statement
    str_l = 'parameter'
    str_r = ';'
    b_couple_nested_flag = 0
    li_tmp, li_match = str_couple_split_verbose_once( li_rem, str_l,str_r,b_couple_nested_flag )
    if( len( li_match )>=1 ):
        for li in li_match:
            li_parm_statement = []
            str_parm = list2str(li); #print( str_parm )
            li_parm_statement.extend( str_parm.split(',') )
            li_parm_raw.extend( li_parm_statement )
    # print( list2str(li_parm_raw) )

    #step2 parse parm raw----
    # li_parm = [] #str_param_name, str_default_val, b_independent_flag
    for s in li_parm_raw:
        left_val = ''
        righ_val = ''
        if( str_find(s,'=') ):
            li = s.split('=')
            left_val = li[0].split()[-1].strip()
            righ_val = li[1].split()[0].strip()
        else:
            left_val = s.split()[-1]
            righ_val = '<must_be_specifed>'
        b_independent_flag = 1
        for li in li_parm:
            key = li[0]
            if( str_find( righ_val, key ) ):
                b_independent_flag = 0
                break
        li_parm.append( [left_val,righ_val,b_independent_flag] )
        # print( 'left_val:{:20s}, righ_val:{:20s}, b_independent_flag:{}'.format( left_val,righ_val,b_independent_flag ) )
    # print( li_parm )

    return li_parm  #[(str_param_name, str_default_val, b_independent_flag), ...]
def get_port_list( li_str_module ):  #[port_name, bit_width, io]
    '''
    * pat1:
    >>>
    module A (
    input A,
    input wire [31:0] B,
    output C
    );
    >>>
    * pat2:
    >>>
    module A #( parameter DW=32 )(
    A,B,
    C
    );
    >>>
    * return: list_port = [port_name, bit_width_declare, io]  #bit_width_declare = [msb:lsb] [msb:lsb]
    '''
    li_port = [] #[(str_port_name, str_bit_width_declre, io_type), ...]     #io_type = [i,o,io,if,??]  #i=input, o=ouput, io=inout, if=interface, ??=unknown
    li_str_module1 = del_all_cmt( li_str_module );  #print( list2str(li_str_module1) )

    str_l = 'module'
    str_r = ';'
    b_couple_nested_flag = 0
    li_tmp = str_couple_split( li_str_module1, str_l,str_r,b_couple_nested_flag )
    li_rem = li_tmp[2]
    li_module_declare = li_tmp[1]; #print( list2str(li_module_declare) )

    #step1 get param list----
    li_port_declare   = [] #  module #( parm_decalre_list ) inst_module ( port_declare_list );
    li_port_statement = [] #  outside module declare,  input ??;

    ##get li_parm_declare
    str_port = ''
    str_l = '('
    str_r = ')'
    b_couple_nested_flag = 1
    li_tmp, li_match = str_couple_split_verbose_once( li_module_declare, str_l,str_r,b_couple_nested_flag )
    if( len( li_match )>1 ):  #module声明中， 当出现两次()被匹配上，则第一次()匹配内容是参数列表，第二次()匹配内容是信号列表
        str_port = list2str(li_match[1])
    else:
        str_port = list2str(li_match[0])
    assert( len(li_match)<=2 )   #module的'参数列表'和'信号列表' 最多被()匹配两次
    li_port_declare.extend( str_port.split(',') ); #print( str_port )
    ##get li_port_statement
    b_port_outside_portlist_flag = 0
    s1 = str_port.split(',')[0] #取端口列表中， 声明第一个信号；  若是input xx,output xx则不用后续再解析；  若是xx,xx， 则需解析端口列表之外的信号定义(input xx; output xx;)；
    if( len(s1.split())==1 ):
        b_port_outside_portlist_flag = 1
    if( b_port_outside_portlist_flag ):
        #找出所有端口列表之外的信号定义(可能匹配到冗余信息)， ['input xx', 'output xx']
        print('NOTICE(), the port define outside port_list declare')
        li_io_type = ['input', 'output', 'inout']
        for io_type in li_io_type:
            str_l = io_type
            str_r = ';'
            b_couple_nested_flag = 0
            li_tmp, li_match = str_couple_split_verbose_once( li_rem, str_l,str_r,b_couple_nested_flag )
            if( len( li_match )>=1 ):
                for li in li_match:
                    str_port = list2str(li); #print( str_port )
                    li_port_statement.append( str_l+' '+str_port )
                # print( list2str(li_port_statement) )
        #把端口定义的 '信号方向'+'位宽声明' 解析
        for p in li_port_declare:
            str_port_name = p.split()[-1]
            str_port_name = deal_port_name( str_port_name )
            assert( len(p.split())==1 )
            str_p_def = ''
            for p_def in li_port_statement:
                if( str_find(p_def, str_port_name) ):
                    str_p_def = p_def
                    break
            str_io_direction, str_bit_width = parse_port_def( str_p_def )
            li_port.append( [str_port_name,str_io_direction,str_bit_width] )
            # print( 'parse port define,  port_name:{:20s}, io:{:20s}, bit_width:{}'.format( str_port_name,str_io_direction,str_bit_width ) )
    else:  #b_port_outside_portlist_flag=0
        for p in li_port_declare:
            str_port_name = p.split()[-1]
            str_port_name = deal_port_name( str_port_name )
            str_io_direction, str_bit_width = parse_port_def( p )
            li_port.append( [str_port_name,str_io_direction,str_bit_width] )
            # print( 'parse port list  ,  port_name:{:20s}, io:{:20s}, bit_width:{}'.format( str_port_name,str_io_direction,str_bit_width ) )

    # for p in li_port:
    #     print( 'port_name:{:20s}, io:{:20s}, bit_width:{}'.format( p[0],p[1],p[2] ) )
    return li_port  #[(str_port_name, str_io_direction, str_bit_width), ...]


#get rtl inst----------------------------------------------------------------------
def get_rtl_inst_str(str_module_name, li_parm, li_port):
    str_wr = ''
    #port wire decalre-------
    li_port_nrm  = []
    li_port_intf = []
    for li in li_port:
        io_type = li[1]
        if( io_type=='if' ):
            li_port_intf.append( li )
        else:
            li_port_nrm.append( li )
    for i in range(len(li_port_nrm)):
        li = li_port_nrm[i]
        port_name = li[0]
        io_type = li[1]
        str_bit_width = li[2]
        str_wr += 'wire {:30s}{:20s};\n'.format( str_bit_width, port_name )
    for i in range(len(li_port_intf)):
        li = li_port_intf[i]
        port_name = li[0]
        io_type = li[1]
        str_bit_width = li[2]
        str_wr += 'interface_t {}{} ();\n'.format( port_name,str_bit_width )
    str_wr += '\n'*1
    #module_name + param_list instance-------
    if( len(li_parm)>0 ):
        str_wr+= '{mod_name} #(\n'.format( mod_name=str_module_name )
        li_parm_independent = []
        li_parm_dependent   = []
        for li in li_parm:
            b_independent_flag = li[2]
            if( b_independent_flag ):
                li_parm_independent.append( li )
            else:
                li_parm_dependent.append( li )
        for i in range(len(li_parm_independent)):
            b_last_flag = i==len(li_parm_independent)-1
            li = li_parm_independent[i]
            parm_name = li[0]
            str_value = li[1]
            str_comma = ','
            if( b_last_flag ):
                str_comma = ' '
            str_wr+= '<indent>.{:30s} ( {:30s}){} //{}\n'.format( parm_name, parm_name,str_comma, str_value )
        str_tmp = ''
        for i in range(len(li_parm_dependent)):
            li = li_parm_dependent[i]
            parm_name = li[0]
            str_value = li[1]
            str_tmp+= '<indent>//.{:30s} ( {:30s}){} //{}\n'.format( parm_name, parm_name,',', str_value )
        # print( str_tmp )
        str_wr+= str_wr.split('\n')[-1]
        str_wr+= ')u_{mod_name}(\n'.format( mod_name=str_module_name )
    else:
        str_wr+= '{mod_name} u_{mod_name}(\n'.format( mod_name=str_module_name )

    #port_list inst
    for i in range(len(li_port)):
        b_last_flag = i==len(li_port)-1
        str_comma = ','
        if( b_last_flag ):
            str_comma = ' '
        li = li_port[i]
        port_name = li[0]
        io_type = li[1]
        str_bit_width = li[2]
        str_wr += '<indent>.{:20s}( {:20s} ){} //{}\n'.format( port_name, port_name, str_comma, io_type )
    str_wr += ');'

    str_pat = '<indent>'
    str_rep = ' '*4
    str_wr  = re.sub(str_pat, str_rep, str_wr, count=0, flags=0); #print( str_wr )

    return str_wr
def gen_rtl_inst(fn_rtl,fn_inst):
    'func: write str_inst to fn_inst file'

    li_module = []
    if( not os.path.isfile(fn_rtl) ):
        print( "NOTICE(), no such file or dictionary:{}".format(fn_rtl) )
        exit(1)
    fp = open(fn_rtl,'rt')
    for s in fp.readlines():
        li_module.append( s.strip('\n\r') )
    fp.close()

    #step1: get all module...endmodule
    li_str_module = del_all_cmt( li_module );  #print( list2str(li_str_module) )
    str_l = 'module'
    str_r = 'endmodule'
    b_couple_nested_flag = 0
    li_tmp, li_match = str_couple_split_verbose_once( li_str_module, str_l,str_r,b_couple_nested_flag )

    #step2: get module_name+parameter_list+port_list + write_to_file
    fp = open(fn_inst,'wt')
    for li_mod in li_match:
        li_module = []
        li_module.append('module')
        li_module.extend( li_mod )
        li_module.append('endmodule'); #print( list2str(li_module) )
        str_l = 'module'
        str_r = '('
        b_couple_nested_flag = 0
        li_res = str_couple_split( li_module, str_l, str_r, b_couple_nested_flag )
        str_module_name = list2str(li_res[1]).split()[0].split('#')[0]; #print( str_module_name )

        li_parm = get_parm_list( li_module )
        li_port = get_port_list( li_module )
        str_wr = 'inst_begin'+'-'*100
        str_inst= get_rtl_inst_str( str_module_name, li_parm, li_port )
        str_wr+= '\n{}\n'.format(str_inst)
        str_wr+= 'inst_end'+'-'*100
        str_wr+= '\n'*4
        fp.write(str_wr)
    fp.close()

#main function----------------------------------------------------------------------
if __name__ == "__main__":
    fn_rtl = ''
    if( len(sys.argv)<2 ):
        print(__doc__)
    else:
        fn_rtl = sys.argv[1]

    if( not os.path.isfile(fn_rtl) ):
        print( 'error! the file %s is not exist\n'%(fn_rtl) )
        #os.system('pause')
        exit(-1)

    fn_inst = 'inst.v'
    gen_rtl_inst(fn_rtl,fn_inst)

    print('generate instance successfully\n')
    #os.system('pause')
