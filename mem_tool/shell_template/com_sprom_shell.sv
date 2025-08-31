/******************************************************************************
*
*  Authors:   moc,dmg
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

module com_sprom_shell#(
parameter  DATA_W   = 32           , //range=[1:], Data width of memory.
parameter  DEPTH    = 64           , //range=[1:], Depth of memory.
parameter  MEM_USER = 0            , //range=[0:], Memory user diy
localparam ADDR_W   = $clog2(DEPTH)  // Address width,
)(
input  wire                   clk    ,
input  wire [`COM_SYS_W-1:0]  sys_cfg,

input  wire                   rd_en   ,
input  wire [ADDR_W-1:0]      rd_addr ,
output wire [DATA_W-1:0]      rd_data//,
);

`ifndef COM_RAM_AS_BBOX
`ifdef COM_RAM_AS_REG
    localparam RAM_AS_REG     = 1;
`else
    localparam RAM_AS_REG     = 0;
`endif

wire use_cell; // use cell as ram.
//------------------------------------------------------------------------------
// Ram logic
//------------------------------------------------------------------------------
generate
    if(RAM_AS_REG) begin: USEREG
        assign use_cell = 1'b0;
    end
    else begin: USECELL
    /*************************************************************************************************/// Start of user logic.
        // if( DEPTH==1024 && DATA_W==128 && MEM_USER==0 )begin
        //     sprom_1024x128_wrapper t_sprom_1024x128_wrapper( .clk(clk),.sys_cfg(sys_cfg), .rd_en(rd_en),.rd_addr(rd_addr),.rd_data(rd_data);
        //     assign use_cell = 1'b1;
        // end
        // else if( DEPTH==1024 && DATA_W==128 && MEM_USER==1 )begin
        //     spram_1024x128_usr1_wrapper t_spram_1024x128_usr1_wrapper( .clk(clk),.sys_cfg(sys_cfg), .rd_en(rd_en),.rd_addr(rd_addr),.rd_data(rd_data);
        //     assign use_cell = 1'b1;
        // end
        if(0) begin
            assign use_cell = 1'b1;
        end
    /*************************************************************************************************/// End of user logic.
        else begin: NFOUND
            `ifndef COM_RAM_NFOUND_CHK
            com_sprom_not_found u_com_sprom_not_found();
            `endif
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
        str_mem_type = "sprom";
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
        str_size = $psprintf("%1dx%1d",DEPTH,DATA_W);
        s = {str_mem_type,str_size,str_user};

        if(use_cell) begin                              // use cell
            $fwrite(fp_mem,"%-20s    Info: normal ram as cell;  %m\n",s);
        end
        else begin                                      // use reg, out of expection
            $fwrite(fp_mem,"%-20s Warning: can't find wrapper;  %m\n",s);
        end
    end
`endif //end of COM_REPORT_ON
`endif //end of ifdef COM_RAM_AS_BBOX

endmodule
