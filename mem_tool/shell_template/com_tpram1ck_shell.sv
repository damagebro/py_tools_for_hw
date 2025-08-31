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

module com_tpram1ck_shell#(
parameter  DATA_W   = 32           , //range=[1:], Data width of memory.
parameter  DEPTH    = 64           , //range=[1:], Depth of memory.
parameter  STRB_W   = 1            , //range=[1:DATA_W], assert(DEPTH%STRB_W==0);  partial_write strobe width,  //assume DATA_W=30bit, STRB_W=2; so => strb[1:0]=2bit, strb[0]->wdata[0*15 +:15], strb[1]->wdata[1*15 +:15];
parameter  MEM_USER = 0            , //range=[0:], Memory user diy
localparam ADDR_W   = $clog2(DEPTH)  // Address width,
)(
input  wire                   clk     ,
input  wire [`COM_SYS_W-1:0]  sys_cfg ,

input  wire [STRB_W-1:0]      wr_en   , //assume DATA_W=30bit, STRB_W=2; so => wr_en[1:0]=2bit, wr_en[0]->wdata[0*15 +:15], wr_en[1]->wdata[1*15 +:15];
input  wire [ADDR_W-1:0]      wr_addr ,
input  wire [DATA_W-1:0]      wr_data ,
input  wire                   rd_en   ,
input  wire [ADDR_W-1:0]      rd_addr ,
output wire [DATA_W-1:0]      rd_data //,
);

`ifndef COM_RAM_AS_BBOX
`ifdef COM_RAM_AS_REG
    localparam RAM_AS_REG     = 1;
`else
    localparam RAM_AS_REG     = 0;
`endif

    localparam MEM_USE_CELL = DEPTH>=30 && DATA_W*DEPTH>=1024;    // You can change the parameters.

//------------------------------------------------------------------------------
// Ram logic
//------------------------------------------------------------------------------
logic use_cell; // use cell as ram.

generate
    if(RAM_AS_REG || !MEM_USE_CELL) begin: USEREG
        com_tpram_reg #(
            .DATA_W (DATA_W ),
            .DEPTH  (DEPTH  ),
            .STRB_W (STRB_W )
        )u_tpram_reg(
            .wr_clk (clk    ),
            .wr_en  (wr_en  ),
            .wr_addr(wr_addr),
            .wr_data(wr_data),
            .rd_clk (clk    ),
            .rd_en  (rd_en  ),
            .rd_addr(rd_addr),
            .rd_data(rd_data)
        );
        assign use_cell = 1'b0;
    end
    else begin: USECELL
    /*************************************************************************************************/// Start of user logic.
        // if( DEPTH==1024 && DATA_W==128 && STRB_W==1 && MEM_USER==0 )begin
        //     tpram1ck_1024x128_wrapper t_tpram1ck_1024x128_wrapper( .clk(clk),.sys_cfg(sys_cfg), .wr_en(wr_en),.wr_addr(wr_addr),.wr_data(wr_data), .rd_en(rd_en),.rd_addr(rd_addr),.rd_data(rd_data);
        //     assign use_cell = 1'b1;
        // end
        // else if( DEPTH==1024 && DATA_W==128 && STRB_W==2 && MEM_USER==0 )begin
        //     tpram1ck_1024x128x2_wrapper t_tpram1ck_1024x128x2_wrapper( .clk(clk),.sys_cfg(sys_cfg), .wr_en(wr_en),.wr_addr(wr_addr),.wr_data(wr_data), .rd_en(rd_en),.rd_addr(rd_addr),.rd_data(rd_data);
        //     assign use_cell = 1'b1;
        // end
        // else if( DEPTH==1024 && DATA_W==128 && STRB_W==1 && MEM_USER==1 )begin
        //     tpram1ck_1024x128_usr1_wrapper t_tpram1ck_1024x128_usr1_wrapper( .clk(clk),.sys_cfg(sys_cfg), .wr_en(wr_en),.wr_addr(wr_addr),.wr_data(wr_data), .rd_en(rd_en),.rd_addr(rd_addr),.rd_data(rd_data);
        //     assign use_cell = 1'b1;
        // end
        if(0) begin
            assign use_cell = 1'b1;
        end
    /*************************************************************************************************/// End of user logic.
        else begin: NFOUND
            `ifdef COM_RAM_NFOUND_CHK
            com_tpram_reg
            `else
            com_tpram1ck_not_found
            `endif
            #(
                .DATA_W (DATA_W ),
                .DEPTH  (DEPTH  ),
                .STRB_W (STRB_W )
            )u_tpram_reg(
                .wr_clk (clk    ),
                .wr_en  (wr_en  ),
                .wr_addr(wr_addr),
                .wr_data(wr_data),
                .rd_clk (clk    ),
                .rd_en  (rd_en  ),
                .rd_addr(rd_addr),
                .rd_data(rd_data)
            );
            assign use_cell = 1'b0;
        end
    end
endgenerate

//------------------------------------------------------------------------------
// Report & Assertion.
//------------------------------------------------------------------------------
`ifdef COM_REPORT_ON
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
        if( MEM_USER!=0 )begin
            str_user = $psprintf("_usr%1d", MEM_USER);
        end
        str_size = STRB_W==1 ? $psprintf("%1dx%1d",DEPTH,DATA_W) : $psprintf("%1dx%1dx%1d",DEPTH,DATA_W,STRB_W);
        s = {str_mem_type,str_size,str_user};

        if(use_cell) begin                              // use cell
            $fwrite(fp_mem,"%-20s    Info: normal ram as cell;  %m\n",s);
        end
        else if(!MEM_USE_CELL) begin                    // use reg, in expection (too small)
            $fwrite(fp_mem,"%-20s Message: small memory as dff; %m\n",s);
        end
        else begin                                      // use reg, out of expection
            $fwrite(fp_mem,"%-20s Warning: can't find wrapper;  %m\n",s);
        end
    end
`endif //end of COM_REPORT_ON
`endif //end of ifdef COM_RAM_AS_BBOX

endmodule
