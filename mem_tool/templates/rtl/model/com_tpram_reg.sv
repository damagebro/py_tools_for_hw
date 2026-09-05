/******************************************************************************
*
*  Authors:   wwq,dmg
*    Email:   dmg@sensetime.com
*     Date:   2025/07/07-20:01:49
*
*  Description:
*  -
*
*  Modify:
*  -
*
******************************************************************************/

module com_tpram_reg #(
parameter  DATA_W   = 32           ,        // Data width of memory.
parameter  DEPTH    = 64           ,        // Depth of memory.
parameter  STRB_W   = 1            ,        // Byte enable width.
localparam ADDR_W   = $clog2(DEPTH)         // Address width,
)(
input  wire                wr_clk ,
input  wire [STRB_W-1:0]   wr_en  ,
input  wire [ADDR_W-1:0]   wr_addr,
input  wire [DATA_W-1:0]   wr_data,

input  wire                rd_clk ,
input  wire                rd_en  ,
input  wire [ADDR_W-1:0]   rd_addr,
output wire [DATA_W-1:0]   rd_data
);

localparam SUB_DW = DATA_W/STRB_W;
reg  [DATA_W-1:0] r_mem[0:DEPTH-1]/*synthesis syn_ramstyle="no_rw_check"*/;
reg  [DATA_W-1:0] r_rd_data;

always@(posedge wr_clk)begin
    for(int i=0; i<STRB_W; i++)
        if(wr_en[i])
            r_mem[wr_addr][i*SUB_DW+:SUB_DW] <= wr_data[i*SUB_DW+:SUB_DW]; //spyglass disable ResetFlop-ML
end
always@(posedge rd_clk)begin
    if(rd_en)
        r_rd_data <= r_mem[rd_addr]; //spyglass disable ResetFlop-ML
end

`ifdef COM_RAM_RD_NOHOLD
    reg  r_rd_en_d;
    assign rd_data = r_rd_en_d ? r_rd_data : 'x;
    always@(posedge rd_clk)begin
        r_rd_en_d <= rd_en;
    end
`else
    assign rd_data = r_rd_data;
`endif

endmodule
