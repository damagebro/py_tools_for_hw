/******************************************************************************
*
*  Authors:   wwq,dmg
*    Email:   dmg@sensetime.com
*     Date:   2025/07/07-20:01:49
*
*  Description:
*  - One-clock true dual-port SRAM implementation shell.
*
******************************************************************************/

module com_tpram1ck_shell #( parameter
    DATA_W   = 32, //range=[1::]
    DEPTH    = 64, //range=[1::]
    STRB_W   = 1,  //range=[1:DATA_W:]
    MEM_USER = 0,
    localparam ADDR_W = $clog2(DEPTH)
)
(
input  wire                         clk                 ,
input  wire [`COM_MEM_CTRL_W-1:0]   i_cfg_mem_ctrl      ,

input  wire [STRB_W-1:0]            i_wr_en             ,
input  wire [ADDR_W-1:0]            i_wr_addr           ,
input  wire [DATA_W-1:0]            i_wr_data           ,
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
localparam MEM_USE_CELL = DEPTH>=30 && DATA_W*DEPTH>=1024;

//signal declare-------------------------------------------------------------
wire [STRB_W-1:0]      u_ram_i_wr_en;
wire [ADDR_W-1:0]      u_ram_i_wr_addr;
wire [DATA_W-1:0]      u_ram_i_wr_data;
wire                   u_ram_i_rd_en;
wire [ADDR_W-1:0]      u_ram_i_rd_addr;
wire [DATA_W-1:0]      u_ram_o_rd_data;
wire                   use_cell;

//statement------------------------------------------------------------------
`ifndef COM_RAM_AS_BBOX
//output assign---
assign o_rd_data = u_ram_o_rd_data;

//body---
assign u_ram_i_wr_en = i_wr_en;
assign u_ram_i_wr_addr = i_wr_addr;
assign u_ram_i_wr_data = i_wr_data;
assign u_ram_i_rd_en = i_rd_en;
assign u_ram_i_rd_addr = i_rd_addr;

generate
if( RAM_AS_REG || !MEM_USE_CELL ) begin:gen_ram_as_reg
    com_tpram_reg #(
        .DATA_W              ( DATA_W             ),
        .DEPTH               ( DEPTH              ),
        .STRB_W              ( STRB_W             )
    )u_com_tpram_reg
    (
        .wr_clk              ( clk                ), //i
        .wr_en               ( u_ram_i_wr_en      ), //i
        .wr_addr             ( u_ram_i_wr_addr    ), //i
        .wr_data             ( u_ram_i_wr_data    ), //i
        .rd_clk              ( clk                ), //i
        .rd_en               ( u_ram_i_rd_en      ), //i
        .rd_addr             ( u_ram_i_rd_addr    ), //i
        .rd_data             ( u_ram_o_rd_data    )  //o
    );
    assign use_cell = 1'b0;
end
else begin:gen_ram_as_cell
// Start of user logic.
    if( 0 ) begin:gen_none
        assign use_cell = 1'b1;
    end
// End of user logic.
    else begin:gen_ram_not_found
        // Enable strict checking to reject any shape without a SRAM PHY.
        `ifdef COM_RAM_NFOUND_CHK
        com_tpram1ck_not_found
        `else
        com_tpram_reg
        `endif
        #(
            .DATA_W          ( DATA_W             ),
            .DEPTH           ( DEPTH              ),
            .STRB_W          ( STRB_W             )
        )u_com_tpram_reg
        (
            .wr_clk          ( clk                ), //i
            .wr_en           ( u_ram_i_wr_en      ), //i
            .wr_addr         ( u_ram_i_wr_addr    ), //i
            .wr_data         ( u_ram_i_wr_data    ), //i
            .rd_clk          ( clk                ), //i
            .rd_en           ( u_ram_i_rd_en      ), //i
            .rd_addr         ( u_ram_i_rd_addr    ), //i
            .rd_data         ( u_ram_o_rd_data    )  //o
        );
        assign use_cell = 1'b0;
    end
end
endgenerate
`endif

//report---------------------------------------------------------------------
// synopsys translate_off
`ifndef COM_REPORT_OFF
integer fp_mem;
string s;
string str_size;
string str_user;
string str_mem_type;
initial begin
    str_mem_type = "tpram1ck";
    fp_mem = $fopen({"./",str_mem_type,".lst"},"wt");
    $fclose(fp_mem);
end
initial begin
    #1;
    fp_mem = $fopen({"./",str_mem_type,".lst"},"at");
    str_user = "";
    if( MEM_USER!=0 )
        str_user = $psprintf("_usr%1d",MEM_USER);
    str_size = STRB_W==1 ? $psprintf("%1dx%1d",DEPTH,DATA_W) :
                           $psprintf("%1dx%1dx%1d",DEPTH,DATA_W,STRB_W);
    s = {str_mem_type,str_size,str_user};

    if( use_cell )
        $fwrite(fp_mem,"%-20s    Info: normal ram as cell;  %m\n",s);
    else if( !MEM_USE_CELL )
        $fwrite(fp_mem,"%-20s Message: small memory as dff; %m\n",s);
    else
        $fwrite(fp_mem,"%-20s Warning: can't find wrapper;  %m\n",s);
end
`endif
// synopsys translate_on
//assert---------------------------------------------------------------------
`ifdef COM_ASSERT_ON
`COM_PARAM_ASSERT( DEPTH>=1, "DEPTH must be larger than 0" )
`COM_PARAM_ASSERT( STRB_W>=1 && DATA_W%STRB_W==0, "DATA_W must be divisible by STRB_W" )
`endif

endmodule //end of com_tpram1ck_shell
