import os,sys,re
from gen_rtl_com import*
from configparser import ConfigParser

def get_eachtype_offset( list_creg, reg_cfg ):
    'ret: aa_typeoffset = [[id_type,off_lo,off_hi],..]; //id_type, 0:dummy 1:cfg/cmd/status, 2:slv, 3:pkg, 4:mem'
    uireg_bitwidth = int(reg_cfg['ATTR']['reg_bitwidth'])
    uireg_bytelen  = int(uireg_bitwidth/8)
    aa_typeoffset = []

    b_init_slv_flag = 1
    id_typelst= -1
    ui_off_lo = 0
    ui_off_hi = 0
    ui_off_lst= 0
    bnew_type_flag = 1
    for idx_creg in range(len(list_creg)):
        reg_last_flag = idx_creg == len(list_creg)-1
        one_creg = list_creg[idx_creg]
        str_type  = one_creg.attr_type
        #print(idx_creg,str_type)

        id_type = 0
        if( str_cmpeq(str_type,'cfg') or str_cmpeq(str_type,'cmd') or str_cmpeq(str_type,'status') ):
            id_type = 1
        elif( str_cmpeq(str_type,'slave') ):
            id_type = 2
        elif( str_cmpeq(str_type,'pkg') ):
            id_type = 3
        elif( str_cmpeq(str_type,'mem') ):
            id_type = 4
        else:
            print( 'NOTICE(), this type not permitted, reg_idx:{idx}, reg_type:{type}'.format(idx=idx_creg,type=str_type) )
            assert( not 'NOTICE(), this type not permitted, reg_idx:{idx}, reg_type:{type}'.format(idx=idx_creg,type=str_type) )

        if( id_typelst == -1 ):
            ui_off_lst= one_creg.addr
            ui_off_lo = one_creg.addr
            ui_off_hi = ui_off_lo
            id_typelst= id_type

        if( id_typelst==1 and id_typelst!=id_type ): #reg->slv
            ui_off_hi = ui_off_lst + uireg_bytelen
            aa_typeoffset.append([id_typelst,ui_off_lo,ui_off_hi])
            if( ui_off_hi != one_creg.addr ):
                aa_typeoffset.append([0,ui_off_hi,one_creg.addr])

            id_typelst = id_type
            ui_off_lo = one_creg.addr
        elif( id_typelst==2 ): #slv->slv,  slv->reg
            ui_off_hi = one_creg.addr
            if( not b_init_slv_flag ):
                aa_typeoffset.append([id_typelst,ui_off_lo,ui_off_hi])

            id_typelst = id_type
            ui_off_lo = one_creg.addr

        b_init_slv_flag = 0
        if( reg_last_flag ):
            ui_rpt_num, b_shd_flag = deal_str_spec(one_creg.attr_spec)
            ui_off_hi = one_creg.addr + uireg_bytelen*ui_rpt_num
            aa_typeoffset.append([id_typelst,ui_off_lo,ui_off_hi])
            if( id_type==1 ):
                aa_typeoffset.append([0,ui_off_hi,0xffff]) #dummy,
        ui_off_lst = one_creg.addr
        # print(idx_creg,id_type,aa_typeoffset)
    #end of for idx_creg
    return aa_typeoffset

def gen_rtl_slv(list_creg, reg_cfg):
    uireg_bitwidth = int(reg_cfg['ATTR']['reg_bitwidth'])

    str_wr = ''
    str_tmp= ''
    aa_typeoffset = get_eachtype_offset(list_creg,reg_cfg)
    list_isreg = get_isreglist(list_creg,reg_cfg)
    b_shadow_reg_flag = check_cfg_shadow(list_isreg)

    #step1: gen base module structure
    str_wr = get_basemodule_str(reg_cfg,"csr_slave")
    str_tmp = str_wr

    #step2: gen parm_list+port_list
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
    # str_port += 'input  wire                     csr_write           ,\n'
    # str_port += 'input  wire [AW-1:0]            csr_addr            ,\n'
    # str_port += 'input  wire [DW-1:0]            csr_wdata           ,\n'
    # str_port += 'input  wire [SW-1:0]            csr_wstrb           ,\n'
    # str_port += 'input  wire                     csr_valid           ,\n'
    # str_port += 'output wire                     csr_ready           ,\n'
    # str_port += 'output wire [DW-1:0]            csr_rdata           ,\n'
    str_portif = 'com_csr_if'
    str_portifm= str_portif + '.master'
    str_portifs= str_portif + '.slave'
    str_port += '{:20s}{:12s}{:20s},\n'.format(str_portifs,'','csr_rxif')

    acnt_type=[0,0,0,0,0]
    for idx_off in range(len(aa_typeoffset)):
        off_last_flag = idx_off==len(aa_typeoffset)-1
        a_off = aa_typeoffset[idx_off] #aa_typeoffset = [[id_type,off_lo,off_hi],..]; //id_type, 0:dummy 1:cfg/cmd/status, 2:slv, 3:pkg, 4:mem'
        id_type= a_off[0]

        acnt_type[id_type] += 1
    #gen csr_txif, //str_slave_name
    list_slv_name = []
    for one_creg in list_creg: #acnt_type[2]: number of slave reg_type
        str_type  = one_creg.attr_type
        if( str_cmpeq(str_type,'slave') ):
            list_slv_name.append( one_creg.regname )
    for idx in range(1,acnt_type[2]+1):
        str_slv_name = list_slv_name[idx-1]
        if( idx==acnt_type[2] and len(list_isreg)==0 ):
            str_port += '{:20s}{:12s}{:20s}//, //{slv_name}'.format(str_portifm,'','csr_txif'+str(idx),slv_name=str_slv_name)
        else:
            str_port += '{:20s}{:12s}{:20s}, //{slv_name}\n'.format(str_portifm,'','csr_txif'+str(idx),slv_name=str_slv_name)
    assert( acnt_type[2]==len(list_slv_name) )

    str1 = get_str_port(list_isreg,reg_cfg,mod_port='tx')
    str_pat = '<indent>'
    str_rep = ' '*0
    str1 = re.sub(str_pat, str_rep, str1, count=0, flags=0)
    str_port += str1

    str_pat = '<port_list>'
    str_rep = str_port
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0); #print(str_tmp)
    str_wr = str_tmp

    #step3: gen i/o mapping
    #get anchor_text insert after wire declare
    str_tmp = str_wr
    str_pat = re.findall('//wire declare.*',str_tmp,flags=0)[0]; #print( str_pat )
    str_rep = str_pat + '\n<anchor_text>'
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)

    #3.1: port S map
    str_anc = ''
    str_anc+= "wire                   csr_write        ;\n"
    str_anc+= "wire [AW-1:0]          csr_addr         ;\n"
    str_anc+= "wire [DW-1:0]          csr_wdata        ;\n"
    str_anc+= "wire [SW-1:0]          csr_wstrb        ;\n"
    str_anc+= "wire                   csr_valid        ;\n"
    str_anc+= "wire                   csr_ready        ;\n"
    str_anc+= "wire [DW-1:0]          csr_rdata        ;\n"
    str_anc+= "assign csr_write   = csr_rxif.csr_write  ;\n"
    str_anc+= "assign csr_addr    = csr_rxif.csr_addr   ;\n"
    str_anc+= "assign csr_wdata   = csr_rxif.csr_wdata  ;\n"
    str_anc+= "assign csr_wstrb   = csr_rxif.csr_wstrb  ;\n"
    str_anc+= "assign csr_valid   = csr_rxif.csr_valid  ;\n"
    str_anc+= "assign csr_rxif.csr_ready   = csr_ready  ;\n"
    str_anc+= "assign csr_rxif.csr_rdata   = csr_rdata  ;\n"

    #3.2: each offset scope
    str_anc+= '\n'*1
    acnt_type=[0,0,0,0,0]
    astr_type=['dmys','regs','slvs','pkgs','mems']
    for idx_off in range(len(aa_typeoffset)):
        off_last_flag = idx_off==len(aa_typeoffset)-1
        a_off = aa_typeoffset[idx_off] #aa_typeoffset = [[id_type,off_lo,off_hi],..]; //id_type, 0:dummy 1:cfg/cmd/status, 2:slv, 3:pkg, 4:mem'
        id_type= a_off[0]
        off_lo = a_off[1]
        off_hi = a_off[2]

        acnt_type[id_type] += 1
        str_anc+= "wire [AW-1:0] csr_offset_{type}_lo = {off_lo};\n".format( type=astr_type[id_type]+str(acnt_type[id_type]), off_lo="'h{:4s}".format(hex(off_lo).split('0x')[-1]) )
        if( not off_last_flag ):
            str_anc+= "wire [AW-1:0] csr_offset_{type}_hi = {off_hi};\n".format( type=astr_type[id_type]+str(acnt_type[id_type]), off_hi="'h{:4s}".format(hex(off_hi).split('0x')[-1]) )

    #3.3: sel
    str_anc+= '\n'*1
    acnt_type=[0,0,0,0,0]
    for idx_off in range(len(aa_typeoffset)):
        off_last_flag = idx_off==len(aa_typeoffset)-1
        a_off = aa_typeoffset[idx_off] #aa_typeoffset = [[id_type,off_lo,off_hi],..]; //id_type, 0:dummy 1:cfg/cmd/status, 2:slv, 3:pkg, 4:mem'
        id_type= a_off[0]

        acnt_type[id_type] += 1
        if( off_last_flag ):
            str_anc+= "wire bcsr_{type}_sel = csr_valid && csr_addr>=csr_offset_{type}_lo;\n".format( type=astr_type[id_type]+str(acnt_type[id_type]) )
        else:
            str_anc+= "wire bcsr_{type}_sel = csr_valid && csr_addr>=csr_offset_{type}_lo && csr_addr<csr_offset_{type}_hi;\n".format( type=astr_type[id_type]+str(acnt_type[id_type]) )
    if( acnt_type[1]==0 ):
        str_anc+= "wire bcsr_regs_sel = 1'b0"
    else:
        str_anc+= "wire bcsr_regs_sel = bcsr_{type}_sel".format( type="regs1" )
    if( acnt_type[1]>1 ):
        for idx in range(2,acnt_type[1]+1):
            str_anc+= " || bcsr_{type}_sel".format( type="regs%d"%(idx) )
    str_anc+= ";\n"

    #3.4: regs + slvs1 + slvs2..
    str_anc+= '\n'*1
    str_anc+= "wire             csr_valid_{type}  = bcsr_{type}_sel ? csr_valid : 1'b0;\n".format( type='regs' )
    str_anc+= "wire [AW-1:0]    csr_addr_{type}   = bcsr_{type}_sel ? {addr}  : {addr_val};\n".format( type='regs',addr="csr_addr", addr_val="{AW{1'b0}}" )
    str_anc+= "wire             csr_ready_{type}  ;\n".format( type='regs' )
    str_anc+= "wire [DW-1:0]    csr_rdata_{type}  ;\n".format( type='regs' )

    if( acnt_type[2] ):
        for idx in range(1,acnt_type[2]+1):
            str_anc+= '\n'*1
            str_anc+= "wire             csr_valid_{typ}  = bcsr_{typ}_sel ? csr_valid : 1'b0;\n".format( typ='slvs%d'%(idx) )
            str_anc+= "wire [AW-1:0]    csr_addr_{typ}   = bcsr_{typ}_sel ? {addr}   : {addr_val};\n".format( typ='slvs%d'%(idx), addr="csr_addr-csr_offset_%s_lo"%('slvs%d'%(idx)), addr_val="{AW{1'b0}}" )
            str_anc+= "wire             csr_ready_{typ}  ;\n".format( typ='slvs%d'%(idx) )
            str_anc+= "wire [DW-1:0]    csr_rdata_{typ} ;\n".format( typ='slvs%d'%(idx) )

    str_pat = '<anchor_text>'
    str_rep = str_anc
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)
    # print(str_tmp)
    str_wr = str_tmp

    #//statement anchor----
    str_tmp = str_wr
    str_pat = re.findall('//statement.*',str_tmp,flags=0)[0]; #print( str_pat )
    str_rep = str_pat + '\n<anchor_text>'
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)

    #step3.5: assign slave, register out/direct out
    if( acnt_type[2] ):
        str_anc = ''
        for idx in range(1,acnt_type[2]+1):
            str_anc+= '\n'*1
            str_anc+= '//assign {slv}---\n'.format( slv='slvs%d'%(idx) )
            if( reg_cfg['ATTR']['slv_register']=='yes' ):
                str_anc += "wire csr_{slv}_ivld = csr_valid_{slv};\n".format( slv='slvs%d'%(idx) )
                str_anc += "wire csr_{slv}_irdy;\n".format( slv='slvs%d'%(idx) )
                str_anc += "wire csr_{slv}_ovld;\n".format( slv='slvs%d'%(idx) )
                str_anc += "wire csr_{slv}_ordy = csr_txif{M}.csr_ready;\n".format( M='%d'%(idx), slv='slvs%d'%(idx) )
                str_anc += "wire csr_{slv}_ihs = csr_{slv}_ivld && csr_{slv}_irdy;\n".format( slv='slvs%d'%(idx) )
                str_anc += "wire csr_{slv}_ohs = csr_{slv}_ovld && csr_{slv}_ordy;\n".format( slv='slvs%d'%(idx) )
                str_anc += "reg  rc_csr_{slv}_busy;\n".format( slv='slvs%d'%(idx) )
                str_anc += "reg           rc_csr_{slv}_write;\n".format( slv='slvs%d'%(idx) )
                str_anc += "reg  [AW-1:0] rc_csr_{slv}_addr;\n".format( slv='slvs%d'%(idx) )
                str_anc += "reg  [DW-1:0] rc_csr_{slv}_wr_data;\n".format( slv='slvs%d'%(idx) )
                str_anc += "reg  [SW-1:0] rc_csr_{slv}_wr_strb;\n".format( slv='slvs%d'%(idx) )
                str_anc += "always @(posedge clk or negedge rst_n)\n"
                str_anc += "begin\n"
                str_anc += "    if( !rst_n ) begin\n"
                str_anc += "        rc_csr_{slv}_busy <= 1'b0;\n".format( slv='slvs%d'%(idx) )
                str_anc += "    end\n"
                str_anc += "    else if( clear ) begin\n"
                str_anc += "        rc_csr_{slv}_busy <= 1'b0;\n".format( slv='slvs%d'%(idx) )
                str_anc += "    end\n"
                str_anc += "    else if( csr_{slv}_ihs ) begin\n".format( slv='slvs%d'%(idx) )
                str_anc += "        rc_csr_{slv}_busy <= 1'b1;\n".format( slv='slvs%d'%(idx) )
                str_anc += "    end\n"
                str_anc += "    else if( csr_{slv}_ohs ) begin\n".format( slv='slvs%d'%(idx) )
                str_anc += "        rc_csr_{slv}_busy <= 1'b0;\n".format( slv='slvs%d'%(idx) )
                str_anc += "    end\n"
                str_anc += "end\n"
                str_anc += "always @(posedge clk or negedge rst_n)\n"
                str_anc += "begin\n"
                str_anc += "    if( !rst_n ) begin\n"
                str_anc += "        {{rc_csr_{slv}_write,rc_csr_{slv}_addr,rc_csr_{slv}_wr_data,rc_csr_{slv}_wr_strb}} <= 'b0;\n".format( slv='slvs%d'%(idx) )
                str_anc += "    end\n"
                str_anc += "    else if( csr_{slv}_ihs ) begin\n".format( slv='slvs%d'%(idx) )
                str_anc += "        {{rc_csr_{slv}_write,rc_csr_{slv}_addr,rc_csr_{slv}_wr_data,rc_csr_{slv}_wr_strb}} <= {{csr_write,csr_addr_{slv},csr_wdata,csr_wstrb}};\n".format( slv='slvs%d'%(idx) )
                str_anc += "    end\n"
                str_anc += "end\n"
                str_anc += "assign csr_{slv}_irdy = (bcsr_{slv}_sel&&(csr_write||rc_csr_{slv}_write)) ? (!rc_csr_{slv}_busy || csr_{slv}_ordy) : !rc_csr_{slv}_busy;\n".format( slv='slvs%d'%(idx) )
                str_anc += "assign csr_{slv}_ovld = rc_csr_{slv}_busy;\n".format( slv='slvs%d'%(idx) )
                str_anc += "assign csr_txif{M}.csr_write  = rc_csr_{slv}_write  ;\n".format( M='%d'%(idx), slv='slvs%d'%(idx) )
                str_anc += "assign csr_txif{M}.csr_addr   = rc_csr_{slv}_addr   ;\n".format( M='%d'%(idx), slv='slvs%d'%(idx) )
                str_anc += "assign csr_txif{M}.csr_wdata  = rc_csr_{slv}_wr_data;\n".format( M='%d'%(idx), slv='slvs%d'%(idx) )
                str_anc += "assign csr_txif{M}.csr_wstrb  = rc_csr_{slv}_wr_strb;\n".format( M='%d'%(idx), slv='slvs%d'%(idx) )
                str_anc += "assign csr_txif{M}.csr_valid  = csr_{slv}_ovld      ;\n".format( M='%d'%(idx), slv='slvs%d'%(idx) )
                str_anc += "assign csr_ready_{slv}    = (bcsr_{slv}_sel&&csr_write) ? csr_{slv}_irdy : (csr_{slv}_ohs&&!rc_csr_{slv}_write);\n".format( slv='slvs%d'%(idx) )
                str_anc += "assign csr_rdata_{slv}   = csr_txif{M}.csr_rdata ;\n".format( M='%d'%(idx), slv='slvs%d'%(idx) )
            else:
                str_anc+= "assign csr_txif{M}.csr_write   = csr_write       ;\n".format( typ='slvs%d'%(idx), M='%d'%(idx) )
                str_anc+= "assign csr_txif{M}.csr_addr    = csr_addr_{typ}  ;\n".format( typ='slvs%d'%(idx), M='%d'%(idx) )
                str_anc+= "assign csr_txif{M}.csr_wdata   = csr_wdata       ;\n".format( typ='slvs%d'%(idx), M='%d'%(idx) )
                str_anc+= "assign csr_txif{M}.csr_wstrb   = csr_wstrb       ;\n".format( typ='slvs%d'%(idx), M='%d'%(idx) )
                str_anc+= "assign csr_txif{M}.csr_valid   = csr_valid_{typ} ;\n".format( typ='slvs%d'%(idx), M='%d'%(idx) )
                str_anc+= "assign csr_ready_{typ}   = csr_txif{M}.csr_ready ;\n".format( typ='slvs%d'%(idx), M='%d'%(idx) )
                str_anc+= "assign csr_rdata_{typ}   = csr_txif{M}.csr_rdata ;\n".format( typ='slvs%d'%(idx), M='%d'%(idx) )

        str_pat = '<anchor_text>'
        str_rep = str_anc + '\n' + '<anchor_text>'
        str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)
        str_wr = str_tmp
    #end of if( acnt_type[2] ), acnt_type[2]>0 mean have csr_slave;

    #step4: DeMux
    str_anc = ''
    str_anc+= '\n'*1
    str_anc+= "wire          csr_ready_dmy   = 1'b1;\n"
    str_anc+= "wire [DW-1:0] csr_rdata_dmy  = {{{muti}{{16'hdeaf}}}};\n".format(muti=int((uireg_bitwidth+15)/16))
    str_anc+= "reg           rb_csr_ready;\n"
    str_anc+= "reg  [DW-1:0] rb_csr_rddata;\n"
    str_anc+= "always @*\n"
    str_anc+= "begin\n"
    # str_anc+= "    if( bcsr_{type}_sel )begin\n".format( type='slvs1' )
    # str_anc+= "    else if( bcsr_{type}_sel )begin\n".format( type='slvs2' )
    if( acnt_type[2] ):
        str_anc+= "    if( bcsr_{type}_sel )begin\n".format( type='slvs1' )
        str_anc+= "        rb_csr_ready = csr_ready_{type};\n".format( type='slvs1' )
        str_anc+= "        rb_csr_rddata= csr_rdata_{type};\n".format( type='slvs1' )
        str_anc+= "    end\n"
        for idx in range(2,acnt_type[2]+1):
            str_anc+= "    else if( bcsr_{type}_sel )begin\n".format( type='slvs'+str(idx) )
            str_anc+= "        rb_csr_ready = csr_ready_{type};\n".format( type='slvs'+str(idx) )
            str_anc+= "        rb_csr_rddata= csr_rdata_{type};\n".format( type='slvs'+str(idx) )
            str_anc+= "    end\n"
        if( acnt_type[1] ):
            str_anc+= "    else if( bcsr_{type}_sel )begin\n".format( type='regs' )
            str_anc+= "        rb_csr_ready = csr_ready_{type};\n".format( type='regs' )
            str_anc+= "        rb_csr_rddata= csr_rdata_{type};\n".format( type='regs' )
            str_anc+= "    end\n"
    elif( acnt_type[1] ):
        str_anc+= "    if( bcsr_{type}_sel )begin\n".format( type='regs' )
        str_anc+= "        rb_csr_ready = csr_ready_{type};\n".format( type='regs' )
        str_anc+= "        rb_csr_rddata= csr_rdata_{type};\n".format( type='regs' )
        str_anc+= "    end\n"
    assert( acnt_type[1]!=0 or acnt_type[2]!=0 )
    str_anc+= "    else begin\n".format( type='slvs2' )
    str_anc+= "        rb_csr_ready = csr_ready_{type};\n".format( type='dmy' )
    str_anc+= "        rb_csr_rddata= csr_rdata_{type};\n".format( type='dmy' )
    str_anc+= "    end\n"
    str_anc+= "end\n"
    str_anc+= "assign csr_ready = rb_csr_ready;\n"
    str_anc+= "assign csr_rdata = rb_csr_rddata;\n"

    #step5: regs_inst
    if( acnt_type[1] ):
        str_anc+= '\n'*1
        str_anc+= "{top}_csr_slave_reg #(\n".format( top=reg_cfg['FILE']['top_name'] )
        str_anc+= "    .AW (AW),\n"
        str_anc+= "    .DW (DW)\n"
        str_anc+= ") u_{top}_csr_slave_reg\n".format( top=reg_cfg['FILE']['top_name'] )
        str_anc+= "(\n"
        str_anc+= "<port_inst>\n"
        str_anc+= ");"

    str_port = ''
    str_port += '    .{:20s}( {:20s} ),\n'.format('clk       ','clk            ')
    str_port += '    .{:20s}( {:20s} ),\n'.format('rst_n     ','rst_n          ')
    str_port += '    .{:20s}( {:20s} ),\n'.format('clear     ','clear          ')
    if( b_shadow_reg_flag ):
        str_port += '    .{:20s}( {:20s} ),\n'.format('shadow_upen','shadow_upen ')
    str_port += '\n'
    str_port += '    .{:20s}( {:20s} ),\n'.format('csr_write  ','csr_write       ')
    str_port += '    .{:20s}( {:20s} ),\n'.format('csr_addr   ','csr_addr_regs   ')
    str_port += '    .{:20s}( {:20s} ),\n'.format('csr_wdata  ','csr_wdata       ')
    str_port += '    .{:20s}( {:20s} ),\n'.format('csr_wstrb  ','csr_wstrb       ')
    str_port += '    .{:20s}( {:20s} ),\n'.format('csr_valid  ','csr_valid_regs  ')
    str_port += '    .{:20s}( {:20s} ),\n'.format('csr_ready  ','csr_ready_regs  ')
    str_port += '    .{:20s}( {:20s} ),\n'.format('csr_rdata  ','csr_rdata_regs  ')

    str1 = get_str_port(list_isreg,reg_cfg,mod_port='inst')
    str_pat = '<indent>'
    str_rep = ' '*4
    str1 = re.sub(str_pat, str_rep, str1, count=0, flags=0)
    str_port += str1

    str_pat = '<port_inst>'
    str_rep = str_port
    str_anc = re.sub(str_pat, str_rep, str_anc, count=0, flags=0)

    str_pat = '<anchor_text>'
    str_rep = str_anc
    str_tmp = re.sub(str_pat, str_rep, str_tmp, count=0, flags=0)
    str_wr = str_tmp
    # print(str_tmp)

    rtldir   = reg_cfg['FILE']['work_dir'] + '/rtl/'
    str_mod  = reg_cfg['FILE']['top_name'] + '_'+'csr_slave'
    filepath = rtldir + str_mod
    filename = filepath + '/%s.sv'%(str_mod)
    if( not os.path.isdir(filepath) ):
        os.makedirs(filepath)
        # cmd = 'cd %s && mkdir %s'%(rtldir,str_mod)
        # os.system(cmd)
    fp = open(filename,'wt')
    fp.write(str_wr)
    fp.close()

    uireg_count = acnt_type[1]
    return uireg_count
