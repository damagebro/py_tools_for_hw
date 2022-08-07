# -*- coding: utf-8 -*-
import os,sys,re

#字符串查找，分割，替换, 列表转字符串----
## ui_find_times = str_find( str_ori, str_pat )
## li_str_splited = str.split(sep=None, maxsplit=-1)
## str_replaced = re.sub(pattern, repl, string, count=0, flags=0)
## str_jointed =  list2str( li_str, str_joint="\n" )

def str_find( str_ori, str_pat ):
    'ret: if str_ori have str_pat, return a integer number, which is larger than 0'
    li_s = str_ori.split( str_pat )
    ui_ret = len( li_s )-1
    # ui_ret = len(re.findall(str_pat,str_ori,flags=0))
    return( ui_ret )
def str_re_find( str_ori, str_pat ):
    'ret: if str_ori have str_pat, return a integer number, which is larger than 0'
    ui_ret = len(re.findall(str_pat,str_ori,flags=0))
    return( ui_ret )
def list2str( li_str, str_joint="\n" ):
    str_ret = ""
    for i in range(len(li_str)):
        s = li_str[i]
        s1 = str_joint
        if( i==len(li_str)-1 ):
            s1 = ''
        str_ret += s + s1

    return str_ret
def get_before_last_split(  s, str_delim='' ):
    'func: get the string before last split delimeter'
    li_split = s.split(str_delim)
    return list2str(li_split[0:len(li_split)-1],str_delim)
# def get_oneline_all_couple_split( s, str_l, str_r ):  #only b_couple_nested_flag=0
#     'ret: [ str_match1, str_match2,... ]'
#     li_ret = []
#     while( str_find( s,str_r )>0 ):
#         li = s.split( str_r,1 )
#         li_ret.append( li[0].split( str_l,1)[1] )
#         s = li[1]

#     return li_ret

#字符串 成对分割符处理----
def oneline_str_nested_couple_parse( s, str_l, str_r, ui_times_left_larger_than_righ ):
    '''
    ui_times_left_larger_than_righ: str_l比str_r多出现的次数
    ret: str_before_matched_str_r, str_after_matched_str_r
    '''
    b_find_flag = 0
    col_idx = len(s)
    for i in range( len(s) ):
        str_pre = s[0:i+1]
        ui_match_times_l = str_find( str_pre, str_l )
        ui_match_times_r = str_find( str_pre, str_r )
        if( ui_match_times_l+ui_times_left_larger_than_righ==ui_match_times_r ):
            b_find_flag = 1
            col_idx = i
            break

    str_pre = ''
    str_lst = ''
    if( b_find_flag ):
        if( col_idx>0 ):
            str_pre = s[0:col_idx]
        str_lst  = s[col_idx:].split( str_r,1 )[-1]
    return [b_find_flag,str_pre,str_lst]

def oneline_str_couple_split( s, str_l, str_r ):
    'ret: li_ret = [ str_pre, str_mid, str_lst ]'
    li_s = s.split( str_l,1 )
    s1 = li_s[1]
    col_idx = len(s1)
    for i in range( len(s1) ):
        str_rem = s1[i:]; #print( str_rem )
        ui_match_times_l = str_find( str_rem, str_l )
        ui_match_times_r = str_find( str_rem, str_r )
        if( ui_match_times_l==ui_match_times_r ):
            col_idx = i
            break

    str_pre = li_s[0]
    str_mid = s1.split(str_r,1)[0]
    str_lst = s1.split(str_r,1)[1]
    # print( "pre:{}\nmid:{}\nlst:{}\n".format(str_pre,str_mid,str_lst) )
    return [str_pre, str_mid, str_lst]

def str_couple_split( li_str, str_l, str_r, b_couple_nested_flag=0 ):
    '''
    li_str: 原始字符串 按行分割后的数组
    str_l: 成对分割符左边部分
    str_r: 成对分割符右边部分
    b_couple_nested_flag: 成对分割符是否嵌套； '/**/块注释'仅匹配一次，不嵌套； '()'使用嵌套规则

    ret: li_ret = [li_pre, li_mid, li_lst]
    li_pre: 第一次str_l之前的所有字符串,按行划分为数组形式
    li_mid: 第一级str_l+str_r之间的所有字符串,按行划分为数组形式; 可能内部还能被成对分割符进行分割。
    li_lst: 与第一次str_l成对的第一次str_r之后的所有字符串,按行划分为数组形式
    '''
    li_pre = []
    li_mid = []
    li_lst = []
    linecnt_l = 0
    linecnt_r = 0
    ui_match_times_l = 0
    #find li_pre
    for s in li_str:
        linecnt_l += 1
        ui_match_times_l = str_find( s, str_l )
        if( ui_match_times_l==0 ):
            li_pre.append(s)
        else:
            li_pre.append( s.split( str_l )[0] )
            break
    if( ui_match_times_l>0 ):
        # find li_mid+li_lst
        ui_match_times_l_sum = 0
        ui_match_times_r_sum = 0
        linecnt_r = linecnt_l-1
        for s in li_str[linecnt_l-1: ]:
            linecnt_r += 1
            ui_match_times_l = str_find( s, str_l )
            ui_match_times_r = str_find( s, str_r )
            if( b_couple_nested_flag ):
                ui_diff = ui_match_times_l_sum-ui_match_times_r_sum
                if( ui_match_times_r>0 and ui_diff>0 ):
                    li_res = oneline_str_nested_couple_parse(s, str_l,str_r, ui_diff)
                    b_find_flag = li_res[0]
                    if( b_find_flag ):
                        li_mid.append( li_res[1] )
                        li_lst.append( li_res[2] )
                        if( linecnt_r<len(li_str) ):
                            li_lst.extend( li_str[linecnt_r:] ); #print( list2str( li_lst ) )
                        break
                else:
                    ui_match_times_l_sum += ui_match_times_l
                    ui_match_times_r_sum += ui_match_times_r
            else:
                ui_match_times_l_sum = 1
                ui_match_times_r_sum += ui_match_times_r

            if( ui_match_times_l_sum!=ui_match_times_r_sum and linecnt_r==linecnt_l and ui_match_times_l>0 ):  #成对分隔符在不同行,记录左分隔符之后所有内容
                li_mid.append( s.split( str_l,1 )[1] ); #print( li_mid )
            if( ui_match_times_l_sum==ui_match_times_r_sum ):
                if( linecnt_r>linecnt_l ):  #成对分割符在不同行
                    li_mid.append( get_before_last_split(s,str_r) )
                    li_lst.append( s.split( str_r )[-1] ); #print( list2str( li_lst ) )
                elif( linecnt_r==linecnt_l ): #成对分割符在相同行
                    li_res = oneline_str_couple_split( s, str_l, str_r )
                    li_mid.append( li_res[1] )
                    li_lst.append( li_res[2] )

                if( linecnt_r<len(li_str) ):
                    li_lst.extend( li_str[linecnt_r:] ); #print( list2str( li_lst ) )
                break
            elif( ui_match_times_l_sum<ui_match_times_r_sum and b_couple_nested_flag==0 ):
                li_tmp = s.split( str_r,1 )
                if( str_find(li_tmp[1],str_l)>=str_find(li_tmp[1],str_r) ):
                    li_mid.append( li_tmp[0] )
                    li_lst.append( li_tmp[1] )
                    if( linecnt_r<len(li_str) ):
                        li_lst.extend( li_str[linecnt_r:] )
                    break
                else:
                    print( "NOTICE(), unnested_couple_split error!!! the right str:'{}' appear more times than left str:'{}'".format(str_r, str_l) )
                    exit(1)
            elif( ui_match_times_l_sum<ui_match_times_r_sum and b_couple_nested_flag==1 ):
                print( "NOTICE(), nested_couple_split error!!! the right str:'{}' appear more times than left str:'{}'".format(str_r, str_l) )
                exit(1)
            if( linecnt_r>linecnt_l ):
                li_mid.append(s)

    # print( '--------ori str-----------------:\n',list2str( li_str ) )
    # print( '--------pre str-----------------:\n',list2str( li_pre ) )
    # print( '--------mid str-----------------:\n',list2str( li_mid ) )
    # print( '--------lst str-----------------:\n',list2str( li_lst ) )
    return [li_pre, li_mid, li_lst]


def str_couple_split_verbose_once( li_str, str_l, str_r, b_couple_nested_flag=0 ):
    'ret: [li_pre, li_mid..., li_lst], [li_match1, li_match2, ...]'
    li_pre = []
    li_mid_tmp = []
    li_match = []

    li_tmp = str_couple_split( li_str, str_l, str_r, b_couple_nested_flag ); #print( li_tmp )
    li_pre.extend( li_tmp[0] )
    if( len(li_tmp[1])>0 ):
        li_match.append( li_tmp[1] )
    li_lst_tmp = li_tmp[2]
    while( len(li_lst_tmp)>0 ):
        li_tmp = str_couple_split( li_lst_tmp, str_l, str_r, b_couple_nested_flag ); #print( li_lst_tmp )
        li_mid_tmp.append( li_tmp[0] ); #print( list2str( li_tmp[0] ) )
        if( len(li_tmp[1])>0 ):
            li_match.append( li_tmp[1] )
        li_lst_tmp = li_tmp[2]
    # print( li_mid_tmp )
    li_ret = []
    li_ret.append( li_pre )
    for li in li_mid_tmp:
        li_ret.append( li )

    # for li in li_ret:
    #     print( '--------verbose once match_outside str-----------------:\n',list2str( li ) )
    # for li in li_match:
    #     print( '--------verbose once match_inside str-----------------:\n',list2str( li ) )

    return li_ret,li_match
def str_couple_split_verbose( lili_str, str_l, str_r, b_couple_nested_flag=0, li_recurse=[] ):
    'lili_str: [ li_str1,li_str2,... ]'  #多个原始字符串组成列表，方便递归实现
    'ret: [ [li_pre_s1, li_mid_s1..., li_lst_s1], [li_pre_s2, li_mid_s2..., li_lst_s2] ]'
    lili_tmp   = []
    lili_match_str = []
    for li in lili_str:
        li_tmp, li_match = str_couple_split_verbose_once( li, str_l, str_r, b_couple_nested_flag )  #li_tmp= [li_pre,li_mid,li_lst]
        lili_tmp.append( li_tmp ); #print( li_tmp )
        lili_match_str.extend( li_match )

    li_recurse.append( lili_tmp )  #print( str_couple_verbose2str(li_recurse) )
    if( len(lili_match_str)>0 ):
        str_couple_split_verbose( lili_match_str, str_l, str_r, b_couple_nested_flag, li_recurse )

    return len( lili_tmp )
def str_couple_verbose2str( li_verbose ):
    pass

# 字符串 成对分割符考虑-------------------------------------------------------------
'''
*字符串 成对结构
|s1_pre
|-----|s2_pre
|-----|------|s3
|-----|s2_lst
|s1_mid
|-----|s2
|s1_lst
示例1: (s1_pre (s2_pre(s3)s2_lst) s1_mid  (s2) s1_lst)   #其他表示方式，都以"示例1"进行转换
示例2: (s1_pre (s2) s1_mid (s2_pre(s3)s2_lst) s1_lst)
示例3: (s1_pre (s2) s1_lst)
示例4: (s1)

*数据结构(simple) 表示方式说明；
li = [li_pre, li_mid, li_lst];  #成对分隔符只在匹配第一次被分割,  li_mid中可能包含第二级分割以及更多级分割的内容。


*数据结构(verbose) 表示方式说明；  //多维数组，且每个维度数组嵌套数组
li =
[
  [ [s1_pre,s1_mid,s1_lst] ]  #第一级分割后，剩余的字符串； 该数组大小表示后续被第二级分割了几次；  //assert( li[0].size()==1 )
  [ [s2_pre,s2_lst], [s2] ]  #(1)第二级分割之后, 剩余的字符串, 允许li[1+].size()>=1。
                              (2)若嵌套的数组大小大于1,说明再次被分割,则继续解析下一级对应的数组位置。 //if li[1+][].size()>1, parse continue
                              (3)直到解析 嵌套的数组大小都为1;  //if all li[1+][].size()==1, stop
  [ [s3] ]  #第三级分割后，剩余的字符串。 根据第二级的顺序，可以明确知道本级的字符串，在第二级的哪次被分割。
]

*示例
1. (abc (123)+(456) d
2. (abc) (123)+(456) (d
3. (abc) (123+(456) (d
4. (abc) (123)+(456 (d
'''


# 字符串函数说明-------------------------------------------------------------------
'''
# 备注
1. 字符串分割， 支持任意字符串；
2. 字符串查找， 因为调用正则表达式,有部分字符串不支持, 比如*
3. 字符串替换， 因为调用正则表达式,有部分字符串不支持, 比如"{}"

# 字符串查找
/*
pattern: 被查找的字符串
string: 原始字符串
flags: 特殊功能， 比如忽略大小时，跨换行符等
*/
ui_find_times = re.findall(pattern, string, flags=0)

# 字符串分割
/*
sep: 分割符
maxsplit: 最大被分割的次数
*/
li_str_splited = str.split(sep=None, maxsplit=-1)

# 字符串替换
/*
pattern: 被查找的字符串
repl: 替换后的字符串
string: 原始字符串
count: 最大替换次数
flags: 特殊功能， 比如忽略大小时，跨换行符等
*/
str_subed = re.sub(pattern, repl, string, count=0, flags=0)
>>>
    str_pat = '<port_list>'
    str_rep = str_port
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0); #print(str_tmp)
>>>
'''
