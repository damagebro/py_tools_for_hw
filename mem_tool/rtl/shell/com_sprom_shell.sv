/******************************************************************************
*
*  Authors:   moc,dmg
*    Email:   dmg@sensetime.com
*     Date:   2025/07/07-20:01:49
*
*  Description:
*  - Single-port ROM implementation shell.
*
******************************************************************************/

module com_sprom_shell #( parameter
    DATA_W   = 32, //range=[1::]
    DEPTH    = 64, //range=[1::]
    MEM_USER = 0,
    localparam ADDR_W = $clog2(DEPTH)
)
(
input  wire                         clk                 ,
input  wire [`COM_MEM_CTRL_W-1:0]   i_cfg_mem_ctrl      ,

input  wire                         i_rd_en             ,
input  wire [ADDR_W-1:0]            i_rd_addr           ,
output wire [DATA_W-1:0]            o_rd_data           //,
);
//localparam-----------------------------------------------------------------
`ifdef COM_RAM_AS_REG
localparam RAM_AS_REG = 1;
`else
localparam RAM_AS_REG = 0;
`endif

//signal declare-------------------------------------------------------------
wire                   u_rom_i_rd_en;
wire [ADDR_W-1:0]      u_rom_i_rd_addr;
wire [DATA_W-1:0]      u_rom_o_rd_data;
wire                   use_cell;

//statement------------------------------------------------------------------
`ifndef COM_RAM_AS_BBOX
//output assign---
assign o_rd_data = u_rom_o_rd_data;

//body---
assign u_rom_i_rd_en = i_rd_en;
assign u_rom_i_rd_addr = i_rd_addr;

generate
if( RAM_AS_REG ) begin:gen_rom_as_reg
    assign u_rom_o_rd_data = '0;
    assign use_cell = 1'b0;
end
else begin:gen_rom_as_cell
// Start of user logic.
    if( 0 ) begin:gen_none
        assign use_cell = 1'b1;
    end
// End of user logic.
    else begin:gen_rom_not_found
        // Enable strict checking to reject any shape without a ROM PHY.
        `ifdef COM_RAM_NFOUND_CHK
        com_sprom_not_found u_com_sprom_not_found();
        `endif
        assign u_rom_o_rd_data = '0;
        assign use_cell = 1'b0;
    end
end
endgenerate

//report---------------------------------------------------------------------
// synopsys translate_off
`ifndef COM_REPORT_OFF
integer fp_mem;
string s;
string str_size;
string str_user;
string str_mem_type;
initial begin
    str_mem_type = "sprom";
    fp_mem = $fopen({"./",str_mem_type,".lst"},"wt");
    $fclose(fp_mem);
end
initial begin
    #1;
    fp_mem = $fopen({"./",str_mem_type,".lst"},"at");
    str_user = "";
    if( MEM_USER!=0 )
        str_user = $psprintf("_usr%1d",MEM_USER);
    str_size = $psprintf("%1dx%1d",DEPTH,DATA_W);
    s = {str_mem_type,str_size,str_user};

    if( use_cell )
        $fwrite(fp_mem,"%-20s    Info: normal ram as cell;  %m\n",s);
    else
        $fwrite(fp_mem,"%-20s Warning: can't find wrapper;  %m\n",s);
end
`endif
// synopsys translate_on
//assert---------------------------------------------------------------------
`ifdef COM_ASSERT_ON
`COM_PARAM_ASSERT( DEPTH>=1, "DEPTH must be larger than 0" )
`endif

endmodule //end of com_sprom_shell
