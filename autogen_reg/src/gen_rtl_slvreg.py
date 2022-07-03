import os,sys,re
from gen_rtl_com import*
from configparser import ConfigParser
from math import log2

def get_slvreg_port_str(list_isreg,reg_cfg,str_mod):
    str_tmp = str_mod
    b_shadow_reg_flag = check_cfg_shadow(list_isreg)

    str_parm = ''
    str_parm += '    AW = 16,\n'
    str_parm += '    DW = 32,\n'
    str_parm += '    SW = DW/8'
    str_pat = '<parm_list>'
    str_rep = str_parm
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)

    str_port = ''
    str_port += 'input  wire                     clk                 ,\n'
    str_port += 'input  wire                     rst_n               ,\n'
    str_port += 'input  wire                     clear               ,\n'
    if( b_shadow_reg_flag ):
        str_port += 'input  wire                     shadow_upen         ,\n'
    str_port += '\n'
    str_port += 'input  wire                     csr_write           ,\n'
    str_port += 'input  wire [AW-1:0]            csr_addr            ,\n'
    str_port += 'input  wire [DW-1:0]            csr_wdata           ,\n'
    str_port += 'input  wire [SW-1:0]            csr_wstrb           ,\n'
    str_port += 'input  wire                     csr_valid           ,\n'
    str_port += 'output wire                     csr_ready           ,\n'
    str_port += 'output wire [DW-1:0]            csr_rdata           ,\n'

    str1 = get_str_port(list_isreg,reg_cfg,mod_port='tx')
    str_pat = '<indent>'
    str_rep = ' '*0
    str1 = re.sub(str_pat, str_rep, str1, count=0, flags=0)
    str_port += str1

    str_pat = '<port_list>'
    str_rep = str_port
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0); #print(str_tmp)

    str_ret = str_tmp; #print(str_ret)
    return(str_ret)
def get_regcfg_str(one_creg):
    str_anc = ''
    str_reg = one_creg.regname
    str_sgl = ''
    str_var = ''

    ui_rpt_num, b_shd_flag = deal_str_spec(one_creg.attr_spec)
    str_repeat = ''
    if( ui_rpt_num>1 ):
        str_repeat = '[%d:0]' % (ui_rpt_num-1)

    str_anc+= '\n//{reg}\n'.format( reg=str_reg )
    if( ui_rpt_num>1 ):
        str_anc+= 'wire {rpt} {reg}_upen;\n'.format( rpt=str_repeat, reg=str_reg )
        for i in range(ui_rpt_num):
            str_anc+= 'assign {reg}_upen[{idx}]= (csr_valid && csr_ready) && csr_write && csr_addr=={reg}_offset[{idx}];\n'.format( reg=str_reg, idx=i )

        #parse repeat n, default value format by csv;
        for idx_sgl in range(len(one_creg.list_signal)):
            a_sgl = one_creg.list_signal[idx_sgl] #[str_signame, str_bits_scope, default_val, str_comment]
            str_sgl = a_sgl[0]
            str_var = str_reg + '_' + str_sgl
            li_init = deal_list_default_val(a_sgl[2])
            ui_len = len(li_init)

            uibw_lo, uibw_hi, oneb_flag = deal_bits_scope(a_sgl[1]); #print( uibw_lo, uibw_hi, oneb_flag )
            ui_hwbw_lo = 0
            ui_hwbw_hi = uibw_hi - uibw_lo
            str_bw = ''
            if( not oneb_flag ):
                str_bw = '[{:d}:0]'.format(ui_hwbw_hi-ui_hwbw_lo)

            str_anc+= 'wire {rpt}{bitw} {var}_default;\n'.format( rpt=str_repeat,bitw=str_bw, var=str_var )
            for i in range(ui_rpt_num):
                str_init  = "'h" + hex(li_init[ clip3(i,0,ui_len-1) ]).split('0x')[-1]
                str_anc+= 'assign {var}_default[{idx}]= {val};\n'.format( var=str_var, idx=i, val=str_init )
    else:
        str_anc+= 'wire {rpt}{reg}_upen = (csr_valid && csr_ready) && csr_write && csr_addr=={reg}_offset;\n'.format( rpt=str_repeat, reg=str_reg )
    for idx_sgl in range(len(one_creg.list_signal)):
        sgl_last_flag = idx_sgl == len(one_creg.list_signal)-1
        a_sgl = one_creg.list_signal[idx_sgl] #[str_signame, str_bits_scope, default_val, str_comment]
        str_sgl = a_sgl[0]
        str_var = str_reg + '_' + str_sgl

        uibw_lo, uibw_hi, oneb_flag = deal_bits_scope(a_sgl[1]); #print( uibw_lo, uibw_hi, oneb_flag )
        ui_hwbw_lo = 0
        ui_hwbw_hi = uibw_hi - uibw_lo

        str_bw = ''
        if( not oneb_flag ):
            str_bw = '[{:d}:0]'.format(ui_hwbw_hi-ui_hwbw_lo)
        str_anc+= 'reg  {bitw} rc{var};\n'.format( bitw=str_repeat+str_bw,var=str_var )
        if( b_shd_flag ):
            str_anc+= 'reg  {bitw} rc{var}_q;\n'.format( bitw=str_repeat+str_bw,var=str_var )

    str_idxsel = ''
    if( ui_rpt_num>1 ):
        str_idxsel = '[gi]'
        str_anc+= 'generate\n'
        str_anc+= 'for( genvar gi=0; gi<{rpt_num}; gi++ ) begin\n'.format( rpt_num=ui_rpt_num )
    for idx_sgl in range(len(one_creg.list_signal)):
        sgl_last_flag = idx_sgl == len(one_creg.list_signal)-1
        a_sgl = one_creg.list_signal[idx_sgl] #[str_signame, str_bits_scope, default_val, str_comment]
        str_sgl = a_sgl[0]
        str_var = str_reg + '_' + str_sgl
        if( b_shd_flag ):
            str_var += '_q'

        uibw_lo, uibw_hi, oneb_flag = deal_bits_scope(a_sgl[1]); #print( uibw_lo, uibw_hi, oneb_flag )
        uibw_lo_mod8 = uibw_lo%8
        ui_hwbw_lo = 0
        ui_hwbw_hi = uibw_hi - uibw_lo
        ui_swbw_lo = uibw_lo
        ui_swbw_hi = uibw_hi

        str_init = ''
        if( ui_rpt_num>1 ):
            str_init  = '{var}_default{str_idx}'.format( var=str_var, str_idx=str_idxsel )
        else:
            ui_init   = deal_default_val(a_sgl[2])
            str_init  = "'h" + hex(ui_init).split('0x')[-1]
        ui_strb   = 0
        str_bw_hw = ''
        str_bw_sw = ''

        #always reg_upen
        str_anc+= 'always @(posedge clk or negedge rst_n)\nbegin\n'
        str_anc+= '    if( !rst_n ) begin\n'
        str_anc+= '        rc{var} <= {init};\n'.format( var=str_var+str_idxsel, init=str_init )
        str_anc+= '    end\n'
        str_anc+= '    else if( clear ) begin\n'
        str_anc+= '        rc{var} <= {init};\n'.format( var=str_var+str_idxsel, init=str_init )
        str_anc+= '    end\n'
        str_anc+= '    else if( {reg}_upen{str_idx} ) begin\n'.format( reg=str_reg, str_idx=str_idxsel )
        # str_anc+= '        if( csr_wstrb[{:d}] )\n'.format( 0 )
        # str_anc+= '            rc{var}{bw_var} <= csr_wdata{bw_sw};\n'.format( var=str_var,bw_var='[7:0]',bw_sw='[7:0]' )
        idx_hwcnt = 0
        for idx_strb in range(int(ui_swbw_lo/8),int(ui_swbw_hi/8+1)):
            x1l = idx_strb*8
            x1h = idx_strb*8+7
            x2l = ui_swbw_lo
            x2h = ui_swbw_hi
            ui_low = 0
            ui_len = 0
            ui_len,ui_low = get_intersection(x1l,x1h,x2l,x2h)
            if(ui_len):
                if( ui_len==1 ):
                    if(oneb_flag):
                        str_bw_hw = ''
                    else:
                        str_bw_hw = '[%d]' % ( max(idx_hwcnt*8-uibw_lo_mod8,ui_hwbw_lo) )
                    str_bw_sw = '[%d]' % ( max(idx_strb *8             ,ui_swbw_lo) )
                else:
                    str_bw_hw = '[%d:%d]' % (min(idx_hwcnt*8+7-uibw_lo_mod8,ui_hwbw_hi),max(idx_hwcnt*8-uibw_lo_mod8,ui_hwbw_lo))
                    str_bw_sw = '[%d:%d]' % (min(idx_strb *8+7             ,ui_swbw_hi),max(idx_strb *8             ,ui_swbw_lo))
                str_anc+= '        if( csr_wstrb[{:d}] )\n'.format( idx_strb )
                str_anc+= '            rc{var}{bw_var} <= csr_wdata{bw_sw};\n'.format( var=str_var+str_idxsel,bw_var=str_bw_hw,bw_sw=str_bw_sw )
            idx_hwcnt += 1
        #end of for idx_strb
        str_anc+= '    end\n'
        str_anc+= 'end\n'

        #always shadow_upen
        if( b_shd_flag ):
            str_var = str_reg + '_' + str_sgl
            str_var_shd = str_reg + '_' + str_sgl + '_q'
            str_anc+= 'always @(posedge clk or negedge rst_n)\nbegin\n'
            str_anc+= '    if( !rst_n ) begin\n'
            str_anc+= '        rc{var} <= {init};\n'.format( var=str_var+str_idxsel, init=str_init )
            str_anc+= '    end\n'
            str_anc+= '    else if( clear ) begin\n'
            str_anc+= '        rc{var} <= {init};\n'.format( var=str_var+str_idxsel, init=str_init )
            str_anc+= '    end\n'
            str_anc+= '    else if( shadow_upen ) begin\n'
            str_anc+= '        rc{var} <= rc{shd_var};\n'.format( var=str_var+str_idxsel, shd_var=str_var_shd+str_idxsel )
            str_anc+= '    end\n'
            str_anc+= 'end\n'
    #end of for idx_sgl
    if( ui_rpt_num>1 ):
        str_anc+= 'end //end of for gi\n'
        str_anc+= 'endgenerate\n'
    for idx_sgl in range(len(one_creg.list_signal)):
        sgl_last_flag = idx_sgl == len(one_creg.list_signal)-1
        str_sgl = one_creg.list_signal[idx_sgl][0] #[str_signame, str_bits_scope, default_val, str_comment]
        str_var = str_reg + '_' + str_sgl

        str_anc+= 'assign {var}R = rc{var};\n'.format( var=str_var )

    str_regcfg = str_anc; #print(str_regcfg)
    return(str_regcfg)
def get_regcmd_str(one_creg):
    str_anc = ''
    str_reg = one_creg.regname
    str_sgl = ''
    str_var = ''

    ui_rpt_num, b_shd_flag = deal_str_spec(one_creg.attr_spec)

    str_anc+= '\n//{reg}\n'.format( reg=str_reg )
    if( ui_rpt_num>1 ):
        str_anc+= 'wire [{rpt_num}:0] ps{reg}WEn;\n'.format( rpt_num=ui_rpt_num-1, reg=str_reg )
        for i in range(ui_rpt_num):
            str_anc+= 'assign ps{reg}WEn]{idx}] = (csr_valid && csr_ready) && csr_write && csr_addr=={reg}_offset[{idx}];\n'.format( reg=str_reg, idx=i )
    else:
        str_anc+= 'wire ps{reg}WEn = (csr_valid && csr_ready) && csr_write && csr_addr=={reg}_offset;\n'.format( reg=str_reg )
    # str_anc+= 'wire ps{reg}REn = (csr_valid && csr_ready) && !csr_write && csr_addr=={reg}_offset;\n'.format( reg=str_reg )
    for idx_sgl in range(len(one_creg.list_signal)):
        sgl_last_flag = idx_sgl == len(one_creg.list_signal)-1
        a_sgl = one_creg.list_signal[idx_sgl] #[str_signame, str_bits_scope, default_val, str_comment]
        str_sgl = a_sgl[0]
        str_var = str_reg + '_' + str_sgl

        uibw_lo, uibw_hi, oneb_flag = deal_bits_scope(a_sgl[1]); #print( uibw_lo, uibw_hi, oneb_flag )
        ui_hwbw_lo = 0
        ui_hwbw_hi = uibw_hi - uibw_lo
        ui_swbw_lo = uibw_lo
        ui_swbw_hi = uibw_hi

        str_bw_sw = ''
        if( oneb_flag ):
            str_bw_sw = '[%d]' % (ui_swbw_lo)
        else:
            str_bw_sw = '[%d:%d]' % (ui_swbw_hi,ui_swbw_lo)

        str_anc+= 'assign {var}OEn = ps{reg}WEn;\n'.format( var=str_var, reg=str_reg )
        if( ui_rpt_num>1 ):
            str_anc+= 'assign {var}O = {{{rpt_num}{{ csr_wdata{bw_sw} }}}};\n'.format( var=str_var, rpt_num=ui_rpt_num, bw_sw=str_bw_sw )
        else:
            str_anc+= 'assign {var}O = csr_wdata{bw_sw};\n'.format( var=str_var, bw_sw=str_bw_sw )

    str_regcmd = str_anc; #print(str_regcmd)
    return(str_regcmd)
def get_tol_reg(list_isreg):
    uireg_cnt  = 0
    uireg_tol  = 0

    for idx_reg in range(len(list_isreg)):
        one_creg = list_isreg[idx_reg]
        if( str_cmpin(one_creg.attr_sw,'R') ):
            ui_rpt_num, b_shd_flag = deal_str_spec(one_creg.attr_spec)
            uireg_cnt += ui_rpt_num
    uireg_tol = uireg_cnt

    return( uireg_tol )
def get_readreg_delc_str1(list_isreg,uireg_bitwidth=32):
    "wire [DW-1:0] rddata_{reg} = {joint_word}"
    str_anc = ''

    for idx_reg in range(len(list_isreg)):
        reg_last_flag = idx_reg == len(list_isreg)-1
        one_creg = list_isreg[idx_reg]
        str_type  = one_creg.attr_type

        if( str_cmpin(one_creg.attr_sw,'R') ):
            str_reg  = one_creg.regname
            str_sgl  = ''
            str_var  = ''

            ui_rpt_num, b_shd_flag = deal_str_spec(one_creg.attr_spec)

            str_rddata = ''
            if( ui_rpt_num>1 ):
                str_rddata = 'wire [{rpt_num}:0][DW-1:0] rddata_{reg};\n'.format( rpt_num=ui_rpt_num-1, reg=str_reg )
            for i in range(ui_rpt_num):
                ui_bw_lst = -1
                str_word_joint = ''
                for idx_sgl in range(len(one_creg.list_signal)):
                    sgl_last_flag = idx_sgl == len(one_creg.list_signal)-1
                    a_sgl = one_creg.list_signal[idx_sgl] #[str_signame, str_bits_scope, default_val, str_comment]
                    str_sgl = a_sgl[0]
                    str_var = str_reg + '_' + str_sgl

                    uibw_lo, uibw_hi, oneb_flag = deal_bits_scope(a_sgl[1]); #print( uibw_lo, uibw_hi, oneb_flag )
                    ui_swbw_lo = uibw_lo
                    ui_swbw_hi = uibw_hi

                    if( ui_bw_lst==-1 and ui_swbw_lo>0 ): #ui_bw_lst==-1 mean first signal in reg;
                        ui_bw_lst = 0
                        str_word_joint = str_word_joint + ",%d'b0" % (ui_swbw_lo-ui_bw_lst)
                    elif( ui_swbw_lo>(ui_bw_lst+1) ):
                        str_word_joint = "%d'b0," % (ui_swbw_lo-(ui_bw_lst+1)) + str_word_joint

                    str_var1 = ''
                    str_comma = ','
                    if( idx_sgl == 0 ):
                        str_comma = ''
                    if( str_cmpeq(str_type,'cfg') ):
                        str_var1 = str_var+'R'
                    elif( str_cmpeq(str_type,'cmd') or str_cmpeq(str_type,'status') ):
                        str_var1 = str_var+'D'

                    if( ui_rpt_num>1 ):
                        str_var1 += '[{idx}]'.format(idx=i)
                    str_word_joint = str_var1+str_comma + str_word_joint; #print(str_word_joint)

                    ui_bw_lst = ui_swbw_hi
                #end of for idx_sgl
                if( (ui_bw_lst+1) < uireg_bitwidth ):
                    str_word_joint = "%d'b0," % (uireg_bitwidth-(ui_bw_lst+1)) + str_word_joint

                if( ui_rpt_num>1 ):
                    str_rddata+= 'assign rddata_{reg}[{idx}] = {dw};\n'.format( reg=str_reg, idx=i, dw='{'+str_word_joint+'}' )
                else:
                    str_rddata = 'wire [DW-1:0] rddata_{reg} = {dw};\n'.format( reg=str_reg,dw='{'+str_word_joint+'}' )
            # print( str_word_joint )
            #end of for ui_rpt_num
            str_anc += str_rddata
        #end of if( str_cmpin(one_creg.attr_sw,'R') )
    #end of for idx_reg, read reg

    str_ret = str_anc; #print(str_ret)
    return( str_ret )
def get_readreg_delc_str2(list_isreg):
    '''
    //flatten
    wire [N-1:0][DW-1:0] a_rddata;
    wire [N-1:0][DW-1:0] a_rdaddr;
    '''
    uireg_cnt  = 0
    uireg_tol  = 0
    str_readreg = ''
    str_readreg+= '\n'*1
    str_readreg+= '//flatten\n'

    #1. get tol readreg cnt;-------
    uireg_tol = get_tol_reg(list_isreg)
    #2. declare a_rddata, a_rdaddr;-------
    str_readreg += 'wire [{reg_num}:0][DW-1:0] a_rddata;\n'.format( reg_num=uireg_tol-1 )
    str_readreg += 'wire [{reg_num}:0][AW-1:0] a_rdaddr;\n'.format( reg_num=uireg_tol-1 )

    #3. assign a_rddata;-------
    uireg_cnt = 0
    for idx_reg in range(len(list_isreg)):
        one_creg = list_isreg[idx_reg]
        str_type  = one_creg.attr_type

        if( str_cmpin(one_creg.attr_sw,'R') ):
            str_reg  = one_creg.regname
            ui_rpt_num, b_shd_flag = deal_str_spec(one_creg.attr_spec)

            if( ui_rpt_num>1 ):
                str_readreg += 'assign a_rddata[{ui_hi}:{ui_lo}] = rddata_{reg};\n'.format( ui_hi=uireg_cnt+ui_rpt_num-1, ui_lo=uireg_cnt, reg=str_reg )
            else:
                str_readreg += 'assign a_rddata[{ui_lo}] = rddata_{reg};\n'.format( ui_lo=uireg_cnt, reg=str_reg )
            uireg_cnt += ui_rpt_num
    #4. assign a_rdaddr;-------
    str_readreg += '\n'
    uireg_cnt = 0
    for idx_reg in range(len(list_isreg)):
        one_creg = list_isreg[idx_reg]
        str_type  = one_creg.attr_type

        if( str_cmpin(one_creg.attr_sw,'R') ):
            str_reg  = one_creg.regname
            ui_rpt_num, b_shd_flag = deal_str_spec(one_creg.attr_spec)

            if( ui_rpt_num>1 ):
                str_readreg += 'assign a_rdaddr[{ui_hi}:{ui_lo}] = {reg}_offset;\n'.format( ui_hi=uireg_cnt+ui_rpt_num-1, ui_lo=uireg_cnt, reg=str_reg )
            else:
                str_readreg += 'assign a_rdaddr[{ui_lo}] = {reg}_offset;\n'.format( ui_lo=uireg_cnt, reg=str_reg )
            uireg_cnt += ui_rpt_num

    str_ret = str_readreg; #print(str_ret)
    return( str_ret )
def get_readreg_rden_str(power_num):
    "rden + rdbusy"
    str_readreg = ''
    str_readreg+= '\n'*1

    #rden
    str_readreg += "//rden-------------\n"
    str_readreg += "wire csr_rden = csr_valid && !csr_write;\n"
    if( power_num>=2 ):
        str_readreg += "reg  csr_rden_d;\n"
        str_readreg += "wire ps_csr_rdhs = csr_valid && csr_ready && !csr_write;\n"
        str_readreg += "reg  ps_csr_rdhs_d;\n"
        str_readreg += "wire ps_csr_rden_fst = (csr_rden &&!csr_rden_d) || (csr_rden && ps_csr_rdhs_d);\n"
        str_readreg += "wire ps_csr_rden_lst = !csr_rden && csr_rden_d;\n"
        str_readreg += "always @(posedge clk or negedge rst_n)\n"
        str_readreg += "begin\n"
        str_readreg += "    if( !rst_n ) begin\n"
        str_readreg += "        csr_rden_d <= 1'b0;\n"
        str_readreg += "        ps_csr_rdhs_d <= 1'b0;\n"
        str_readreg += "    end\n"
        str_readreg += "    else begin\n"
        str_readreg += "        csr_rden_d <= csr_rden;\n"
        str_readreg += "        ps_csr_rdhs_d <= ps_csr_rdhs;\n"
        str_readreg += "    end\n"
        str_readreg += "end\n"

    if( power_num>=2 ):
        str_readreg+= '\n'*1
        str_readreg += "reg  [{pow}-1:0] arcb_rden;\n".format( pow=power_num-1 )
        str_readreg += "wire [{pow}-0:0] ab_rden = {{arcb_rden,ps_csr_rden_fst}};\n".format( pow=power_num-1 )
        str_readreg += "always @(posedge clk or negedge rst_n)\n"
        str_readreg += "begin\n"
        str_readreg += "    if( !rst_n ) begin\n"
        str_readreg += "        arcb_rden <= 'b0;\n"
        str_readreg += "    end\n"
        str_readreg += "    else begin\n"
        str_readreg += "        arcb_rden <= ab_rden[{pow}-1:0];\n".format( pow=power_num-1 )
        str_readreg += "    end\n"
        str_readreg += "end\n"

    #rdbusy
    str_readreg+= '\n'*1
    if( power_num>=2 ):
        str_readreg += "reg  rcb_csr_rdbusy;\n"
        str_readreg += "wire b_csr_rdbusy = ps_csr_rden_fst || rcb_csr_rdbusy;\n"
        str_readreg += "always @(posedge clk or negedge rst_n)\n"
        str_readreg += "begin\n"
        str_readreg += "    if( !rst_n ) begin\n"
        str_readreg += "        rcb_csr_rdbusy <= 1'b0;\n"
        str_readreg += "    end\n"
        str_readreg += "    else if( clear ) begin\n"
        str_readreg += "        rcb_csr_rdbusy <= 1'b0;\n"
        str_readreg += "    end\n"
        str_readreg += "    else if( ps_csr_rden_fst ) begin\n"
        str_readreg += "        rcb_csr_rdbusy <= 1'b1;\n"
        str_readreg += "    end\n"
        str_readreg += "    else if( ps_csr_rdhs ) begin\n"
        str_readreg += "        rcb_csr_rdbusy <= 1'b0;\n"
        str_readreg += "    end\n"
        str_readreg += "end\n"

    str_ret = str_readreg; #print(str_ret)
    return( str_ret )
def get_readreg_rdflag_str(list_isreg, uipower_base=32, uipower_num=1):
    "rdflag, rddata"
    str_readreg = ''
    uireg_tol = get_tol_reg(list_isreg)
    power_base = uipower_base  #must 2 **N;
    power_num  = uipower_num

    str_readreg += '\n//rdflag stage0\n'
    #rdflag_s0
    str_readreg+= "reg  [{tol}:0] arbb_rdflag_s0;\n".format( tol=uireg_tol-1 )
    str_readreg+= "always @*\n"
    str_readreg+= "begin\n"
    str_readreg+= "    for ( int i=0; i<{tol}; i++ ) begin\n".format( tol=uireg_tol )
    str_readreg+= "        arbb_rdflag_s0[i] = csr_addr==a_rdaddr[i];\n"
    str_readreg+= "    end\n"
    str_readreg+= "end\n"

    #rdflag_sn, rddata_sn, n>=1
    str_rddata = ''
    str_rdflag = ''
    uireg_iter = uireg_tol
    uireg_iter_lst = uireg_tol
    for power_ord in range(1,power_num):
        uireg_iter = int( (uireg_iter +power_base-1)/(power_base) ); #print( "power_ord:%d, uireg_iter:%d"%(power_ord,uireg_iter) )
        if( power_ord==1 ):
            str_rddata = 'a_rddata'
            str_rdflag = 'arbb_rdflag_s0'
        else:
            str_rddata = "arc_rddata_s{ord_m1}".format( ord_m1=power_ord-1 )
            str_rdflag = "arcb_rdflag_s{ord_m1}".format( ord_m1=power_ord-1 )

        str_readreg += '\n//rdflag+rddata, stage{ord}\n'.format( ord=power_ord )
        str_readreg += "reg  [{tol}:0][DW-1:0]  arb_rddata_s{ord};\n".format( tol=uireg_iter-1, ord=power_ord )
        str_readreg += "reg  [{tol}:0][DW-1:0]  arc_rddata_s{ord};\n".format( tol=uireg_iter-1, ord=power_ord )
        str_readreg += "reg  [{tol}:0] arbb_rdflag_s{ord};\n".format( tol=uireg_iter-1, ord=power_ord )
        str_readreg += "reg  [{tol}:0] arcb_rdflag_s{ord};\n".format( tol=uireg_iter-1, ord=power_ord )
        str_readreg += "always @*\n"
        str_readreg += "begin\n"
        str_readreg += "    arb_rddata_s{ord} = 'b0;\n".format( ord=power_ord )
        str_readreg += "    arbb_rdflag_s{ord}= 'b0;\n".format( ord=power_ord )
        str_readreg += "    for ( int i=0; i<{tol_lst}; i++ ) begin\n".format( tol_lst=uireg_iter_lst )
        str_readreg += "        if( {str_rdflag}[i] ) begin\n".format( str_rdflag=str_rdflag )
        str_readreg += "            arb_rddata_s{ord} [ i>>{log_base} ] = {str_rddata}[i];\n".format( ord=power_ord, log_base=int( log2(power_base) ), str_rddata=str_rddata  )
        str_readreg += "            arbb_rdflag_s{ord}[ i>>{log_base} ] = 1'b1;\n".format( ord=power_ord, log_base=int( log2(power_base) ) )
        str_readreg += "        end\n"
        str_readreg += "    end\n"
        str_readreg += "end\n"
        str_readreg += "always @(posedge clk or negedge rst_n)\n"
        str_readreg += "begin\n"
        str_readreg += "    if( !rst_n ) begin\n"
        str_readreg += "        arc_rddata_s{ord} <= 'b0;\n".format( ord=power_ord )
        str_readreg += "        arcb_rdflag_s{ord} <= 'b0;\n".format( ord=power_ord )
        str_readreg += "    end\n"
        str_readreg += "    else if( ab_rden[{ord_m1}] )begin\n".format( ord_m1=power_ord-1 )
        str_readreg += "        arc_rddata_s{ord} <= arb_rddata_s{ord};\n".format( ord=power_ord )
        str_readreg += "        arcb_rdflag_s{ord} <= arbb_rdflag_s{ord};\n".format( ord=power_ord )
        str_readreg += "    end\n"
        str_readreg += "end\n"

        uireg_iter_lst = uireg_iter

    #rddata_out
    str_rden = ''
    if( power_num==1 ):
        str_rden = "csr_rden"
        str_rddata = 'a_rddata'
        str_rdflag = 'arbb_rdflag_s0'
    else:
        str_rden = "ab_rden[{ord_m1}]".format( ord_m1=power_num-1 )
        str_rddata = "arc_rddata_s{ord_m1}".format( ord_m1=power_num-1 )
        str_rdflag = "arcb_rdflag_s{ord_m1}".format( ord_m1=power_num-1 )
    str_readreg += '\n//rbcsr_rddata\n'
    str_readreg += "reg  [DW-1:0] rbcsr_rddata;\n"
    str_readreg += "always @*\n"
    str_readreg += "begin\n"
    str_readreg += "    rbcsr_rddata = 'b0;\n"
    str_readreg += "    if( {str_rden} )begin\n".format( str_rden=str_rden )
    str_readreg += "        for ( int i=0; i<{tol_lst}; i++ ) begin\n".format( tol_lst=uireg_iter_lst )
    str_readreg += "            if( {str_rdflag}[i] )begin\n".format( str_rdflag=str_rdflag )
    str_readreg += "                rbcsr_rddata = {str_rddata}[i];\n".format( str_rddata=str_rddata )
    str_readreg += "            end\n"
    str_readreg += "        end\n"
    str_readreg += "    end\n"
    str_readreg += "end\n"

    str_ret = str_readreg; #print(str_ret)
    return( str_ret )

def get_readreg_str(list_isreg,uireg_bitwidth=32):
    str_anc = ''
    uipower_base = 32

    uireg_tol = get_tol_reg(list_isreg)
    power_base = uipower_base  #must 2 **N;
    power_num  = 1
    power_order= 1  #32^1,  power_base **power_order

    while( (power_base**power_order)<uireg_tol ):
        power_order += 1
    power_num = power_order; #print( "power_num:",power_num )

    str_anc+= get_readreg_delc_str1(list_isreg,uireg_bitwidth=uireg_bitwidth)
    str_anc+= get_readreg_delc_str2(list_isreg)
    str_anc+= get_readreg_rden_str(power_num)
    str_anc+= get_readreg_rdflag_str(list_isreg,power_base,power_num)

    #step7: assign port
    str_anc+= '\n//csr interface\n'
    if( power_num>=2 ):
        str_anc += "assign csr_ready = b_csr_rdbusy ? ab_rden[{ord_m1}] : 1'b1;\n".format( ord_m1=power_num-1 )
    else:
        str_anc+= "assign csr_ready  = 1'b1;\n"
    str_anc+= "assign csr_rdata = rbcsr_rddata;\n"

    str_readreg = str_anc; #print(str_readreg)
    return(str_readreg)

def get_intersection(x1l,x1h, x2l,x2h):
    'ret: ui_len,ui_low'
    ui_len = 0
    ui_low = 0
    if( x1h<x2l ):
        ui_len = 0
    elif( x1l<x2l and x1h>=x2l ):
        if( x1h<=x2h ):
            ui_len = x1h-x2l+1
            ui_low = x2l
        elif( x1h>x2h ):
            ui_len = x2h-x2l+1
            ui_low = x2l
    elif( x1l>=x2l and x1l<=x2h ):
        if( x1h<=x2h ):
            ui_len = x1h-x1l+1
            ui_low = x1l
        elif( x1h>x2h ):
            ui_len = x2h-x1l+1
            ui_low = x1l
    elif( x1l>x2h ):
        ui_len = 0
    return(ui_len,ui_low)

def gen_rtl_slvreg(list_creg, reg_cfg):
    uireg_bitwidth = int(reg_cfg['ATTR']['reg_bitwidth'])

    str_wr = ''
    str_tmp= ''
    list_isreg = get_isreglist(list_creg,reg_cfg)

    #step1: gen base structure
    str_mod = get_basemodule_str(reg_cfg,"csr_slave_reg")
    #step2: gen parm_list+port_list
    str_wr = get_slvreg_port_str(list_isreg,reg_cfg,str_mod)

    #step3: gen each offset
    #get anchor_text insert after wire declare
    str_tmp = str_wr
    str_pat = re.findall('//wire declare.*',str_tmp,flags=0)[0]; #print( str_pat )
    str_rep = str_pat + '\n<anchor_text>'
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)

    str_anc = ''
    for idx_reg in range(len(list_isreg)):
        reg_last_flag = idx_reg == len(list_isreg)-1
        one_creg = list_isreg[idx_reg]
        str_type  = one_creg.attr_type
        if( str_cmpeq(str_type,'cfg') or str_cmpeq(str_type,'cmd') or str_cmpeq(str_type,'status') ):
            str_reg = one_creg.regname
            str_off = "'h" + hex(one_creg.addr).split('0x')[-1]; #print(str_off)
            ui_rpt_num, b_shd_flag = deal_str_spec(one_creg.attr_spec)
            if( ui_rpt_num>1 ):
                str_anc+= 'wire [{rpt}:0][AW-1:0] {reg}_offset;\n'.format( rpt=ui_rpt_num-1 ,reg=str_reg )
                for i in range(ui_rpt_num):
                    str_off = "'h" + hex(one_creg.addr+int(uireg_bitwidth/8)*i).split('0x')[-1]
                    str_anc+= 'assign {reg}_offset[{idx}] = {offset};\n'.format( reg=str_reg, idx=i, offset=str_off )
            else:
                if( reg_last_flag ):
                    str_anc+= 'wire [AW-1:0] {reg}_offset = {offset};'.format( reg=str_reg, offset=str_off )
                else:
                    str_anc+= 'wire [AW-1:0] {reg}_offset = {offset};\n'.format( reg=str_reg, offset=str_off )
    str_pat = '<anchor_text>'
    str_rep = str_anc
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)

    #step456_pre: get anchor_text insert after statement
    str_pat = re.findall('//statement.*',str_tmp,flags=0)[0]; #print( str_pat )
    str_rep = str_pat + '\n<anchor_text>'
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)

    str_anc = ''
    for idx_reg in range(len(list_isreg)):
        reg_last_flag = idx_reg == len(list_isreg)-1
        one_creg = list_creg[idx_reg]
        str_type  = one_creg.attr_type
        ui_rpt_num, b_shd_flag = deal_str_spec(one_creg.attr_spec)
        #step4: gen cfg
        if( str_cmpeq(str_type,'cfg') ):
            str_anc += get_regcfg_str(one_creg)
        #end of if( str_cmpeq(str_type,'cfg') )

        #step5: gen cmd
        if( str_cmpeq(str_type,'cmd') ):
            str_anc += get_regcmd_str(one_creg)
        #end of if( str_cmpeq(str_type,'cmd') )

        #step5.1: gen status attr_sw: WO|W1C
        if( str_cmpeq(str_type,'status') and str_cmpin(one_creg.attr_sw,'WO|W1C|R1C|RW') ):
            str_anc += get_regcmd_str(one_creg)
        #end of if( str_cmpeq(str_type,'status') )
    #end of for idx_reg, gen

    #step6: read reg
    str_anc+= '\n//read reg\n'
    str_anc+= get_readreg_str(list_isreg,uireg_bitwidth)

    str_pat = '<anchor_text>'
    str_rep = str_anc
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)
    str_wr = str_tmp
    # print(str_tmp)

    rtldir   = reg_cfg['FILE']['work_dir'] + '/rtl/'
    str_mod  = reg_cfg['FILE']['top_name'] + '_'+'csr_slave'
    filepath = rtldir + str_mod
    filename = filepath + '/%s_reg.sv'%(str_mod)
    if( not os.path.isdir(filepath) ):
        os.makedirs(filepath)
        # cmd = 'cd %s && mkdir %s'%(rtldir,str_mod)
        # os.system(cmd)
    fp = open(filename,'wt')
    fp.write(str_wr)
    fp.close()
