/******************************************************************************
*
*  Authors:   dmg
*    Email:   dmg@sensetime.com
*     Date:   2019/11/06-09:56:24
*
*  Description:
*  -
*
*  Modify:
*  -2020/09/21, modify by ty:
*   when rd_empty, rd_data=0; to prevent x_state propagate
*
******************************************************************************/

`ifndef com_sync_fifo_reg_v
`define com_sync_fifo_reg_v
module com_sync_fifo_reg #( parameter
    DW    = 8,
    DEPTH = 4,
    //localparam in param_list feature support after verilog2009, need verdi "-2009" option; to prevant localparam ambiguous in eda software, still use parameter bellow:
    parameter CW = $clog2(DEPTH+1)
)
(
input  wire                     clk                 ,
input  wire                     rst_n               ,
input  wire                     clear               ,

input  wire                     wr_en               ,
input  wire [DW-1:0]            wr_data             ,
output wire                     wr_full             ,
input  wire                     rd_en               ,
output wire [DW-1:0]            rd_data             ,
output wire                     rd_empty            ,
output wire [CW-1:0]            water_level         //,
);
//localparam-----------------------------------------------------------------
localparam AW = $clog2(DEPTH>2?DEPTH:2);
//reg  declare---------------------------------------------------------------
reg  [AW-0:0] r_wrcnt;
reg  [AW-0:0] r_rdcnt;
reg           r_wr_full;
reg           r_rd_empty;
reg  [CW-1:0] r_water_level;
reg  [DEPTH-1:0][DW-1:0] r_mem;
//wire declare---------------------------------------------------------------
//statement------------------------------------------------------------------
//wrcnt
wire [AW-0:0] wrcnt_p1  = r_wrcnt[AW-1:0] + 1'b1;
wire [AW-0:0] wrcnt_nxt = wrcnt_p1==DEPTH[AW-0:0] ? { !r_wrcnt[AW],{AW{1'b0}} } : {r_wrcnt[AW],wrcnt_p1[AW-1:0]};
wire [AW-0:0] wrcnt_tmp = wr_en ? wrcnt_nxt : r_wrcnt;
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n )
        r_wrcnt <= '0;
    else if( clear )
        r_wrcnt <= '0;
    else if( wr_en && !r_wr_full )
        r_wrcnt <= wrcnt_nxt;
end

//rdcnt
wire [AW-0:0] rdcnt_p1  = r_rdcnt[AW-1:0] + 1'b1;
wire [AW-0:0] rdcnt_nxt = rdcnt_p1==DEPTH[AW-0:0] ? { !r_rdcnt[AW],{AW{1'b0}} } : {r_rdcnt[AW],rdcnt_p1[AW-1:0]};
wire [AW-0:0] rdcnt_tmp = rd_en ? rdcnt_nxt : r_rdcnt;
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n )
        r_rdcnt <= '0;
    else if( clear )
        r_rdcnt <= '0;
    else if( rd_en && !r_rd_empty )
        r_rdcnt <= rdcnt_nxt;
end

//full&empty
wire tmp_full = (wrcnt_tmp[AW-1:0]==rdcnt_tmp[AW-1:0]) && (wrcnt_tmp[AW]==!rdcnt_tmp[AW]);
wire tmp_empty= (wrcnt_tmp[AW-0:0]==rdcnt_tmp[AW-0:0]);
wire [AW-0:0] depth_max = DEPTH[AW:0];
wire [AW-0:0] equ_wl = depth_max + {1'b0,rdcnt_tmp[AW-1:0]} - {1'b0,wrcnt_tmp[AW-1:0]};
wire [AW-0:0] neq_wl = {1'b0,rdcnt_tmp[AW-1:0]} - {1'b0,wrcnt_tmp[AW-1:0]};
wire [AW-0:0] tmp_wl = (wrcnt_tmp[AW]==rdcnt_tmp[AW]) ? equ_wl : neq_wl;
assign wr_full   = r_wr_full;
assign rd_empty  = r_rd_empty;
assign water_level = r_water_level;
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n )begin
        r_wr_full <= 1'b0;
        r_rd_empty<= 1'b1;
        r_water_level <= DEPTH[CW-1:0];
    end
    else if( clear )begin
        r_wr_full <= 1'b0;
        r_rd_empty<= 1'b1;
        r_water_level <= DEPTH[CW-1:0];
    end
    else if( rd_en || wr_en )begin
        r_wr_full <= tmp_full;
        r_rd_empty<= tmp_empty;
        r_water_level <= CW'(tmp_wl);
    end
end

//fifo_mem
wire [AW-1:0] wr_addr = r_wrcnt[AW-1:0];
wire [AW-1:0] rd_addr = r_rdcnt[AW-1:0];
assign rd_data = r_mem[rd_addr];
always @(posedge clk)
begin
    if( wr_en && !r_wr_full ) begin
        r_mem[ wr_addr ] <= wr_data;
    end
end

//assert--------------------------------------
// `COM_PARAM_ASSERT( DEPTH>0, "fifo depth must larger than 0" );
// `COM_SIGNAL_ASSERT_LITE( a0, wr_en,!wr_full , "fifo write when full"  );
// `COM_SIGNAL_ASSERT_LITE( a1, rd_en,!rd_empty, "fifo read when empty"  );

endmodule //end of com_sync_fifo_reg
`endif //end of com_sync_fifo_reg_v
