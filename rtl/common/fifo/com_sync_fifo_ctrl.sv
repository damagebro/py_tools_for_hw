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
*
******************************************************************************/

`ifndef com_sync_fifo_ctrl_v
`define com_sync_fifo_ctrl_v
module com_sync_fifo_ctrl #( parameter
    DEPTH   = 4,
    AW      = $clog2(DEPTH+1)
)
(
input  wire                     clk                 ,
input  wire                     rst_n               ,
input  wire                     clear               ,

input  wire                     wr_en               ,
output wire [AW-1:0]            wr_addr             ,
output wire                     wr_full             ,
input  wire                     rd_en               ,
output wire [AW-1:0]            rd_addr             ,
output wire                     rd_empty            ,
output wire [AW-1:0]            water_level         //,
);
//localparam-----------------------------------------------------------------
// localparam AW = $clog2(DEPTH+1);
`COM_PARAM_ASSERT( DEPTH>0, "fifo depth must larger than 0" );
//reg  declare---------------------------------------------------------------
reg  [AW-0:0] rc_wrcnt;
reg  [AW-0:0] rc_rdcnt;
//wire declare---------------------------------------------------------------
wire full;
wire empty;
//statement------------------------------------------------------------------
//wrcnt
wire [AW-0:0] wrcnt_p1  = rc_wrcnt[AW-1:0] + 1'b1; //spyglass disable W164b
wire [AW-0:0] wrcnt_nxt = wrcnt_p1==DEPTH[AW-0:0] ? { !rc_wrcnt[AW],{AW{1'b0}} } : {rc_wrcnt[AW],wrcnt_p1[AW-1:0]}; //spyglass disable W164b
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n ) begin
        rc_wrcnt <= 'b0;
    end
    else if( clear ) begin
        rc_wrcnt <= 'b0;
    end
    else if( wr_en && !full ) begin
        rc_wrcnt <= wrcnt_nxt;
    end
end

//rdcnt
wire [AW-0:0] rdcnt_p1  = rc_rdcnt[AW-1:0] + 1'b1; //spyglass disable W164b
wire [AW-0:0] rdcnt_nxt = rdcnt_p1==DEPTH[AW-0:0] ? { !rc_rdcnt[AW],{AW{1'b0}} } : {rc_rdcnt[AW],rdcnt_p1[AW-1:0]};
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n ) begin
        rc_rdcnt <= 'b0;
    end
    else if( clear ) begin
        rc_rdcnt <= 'b0;
    end
    else if( rd_en && !empty ) begin
        rc_rdcnt <= rdcnt_nxt;
    end
end

//full&empty
assign full = (rc_wrcnt[AW-1:0]==rc_rdcnt[AW-1:0]) && (rc_wrcnt[AW]==!rc_rdcnt[AW]);
assign empty= (rc_wrcnt[AW-0:0]==rc_rdcnt[AW-0:0]);

assign wr_full   = full;
assign rd_empty  = empty;
assign wr_addr = rc_wrcnt[AW-1:0];
assign rd_addr = rc_rdcnt[AW-1:0];

wire [AW-0:0] minus = {1'b0,rc_rdcnt[AW-1:0]} - {1'b0,rc_wrcnt[AW-1:0]};
wire [AW-0:0] comp  = $signed(minus) + $signed({1'b0,DEPTH[AW-0:0]});
wire [AW-0:0]    wl = (rc_wrcnt[AW]==rc_rdcnt[AW]) ? comp : minus;
assign water_level = wl;

//assert--------------------------------------
`COM_SIGNAL_ASSERT_LITE( a0, wr_en,!wr_full , "fifo write when full"  );
`COM_SIGNAL_ASSERT_LITE( a1, rd_en,!rd_empty, "fifo read when empty"  );

endmodule //end of com_sync_fifo_ctrl
`endif //end of com_sync_fifo_ctrl_v
