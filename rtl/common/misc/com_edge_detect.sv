/******************************************************************************
*
*  Authors:   dmg
*    Email:   dmg@sensetime.com
*     Date:   2021/12/03-13:56:35
*
*  Description:
*  -
*
*  Modify:
*  -
*
******************************************************************************/

`ifndef com_edge_detect_v
`define com_edge_detect_v
module com_edge_detect #( parameter
    MODE = "pos" // "pos"|"posedge", "neg"|"negedge", "dual"|"dualedge"
)
(
input  wire                     clk                 ,
input  wire                     rst_n               ,

input  wire                     level_in            ,
output wire                     pulse_out           //,
);
//localparam-----------------------------------------------------------------
`COM_PARAM_ASSERT( MODE=="pos"||MODE=="posedge" || MODE=="neg"||MODE=="negedge" || MODE=="dual"||MODE=="dualedge", "illegal MODE" ); //spyglass disable W193
//reg  declare---------------------------------------------------------------
//wire declare---------------------------------------------------------------
//statement------------------------------------------------------------------
wire d = level_in;
reg  rc_d;
always @(posedge clk or negedge rst_n)
begin
    if( !rst_n )
        rc_d <= 1'b0;
    else
        rc_d <= d;
end

wire ps_posedge = d && !rc_d;
wire ps_negedge =!d &&  rc_d;
wire ps_dualedge= d ^ rc_d;

generate
    if( MODE=="pos" || MODE=="posedge" )begin:gen_pos
        assign pulse_out = ps_posedge;
    end
    else if( MODE=="neg" || MODE=="negedge" )begin:gen_neg
        assign pulse_out = ps_negedge;
    end
    else if( MODE=="dual" || MODE=="dualedge" )begin:gen_dual
        assign pulse_out = ps_dualedge;
    end
    else begin:gen_err
        assign pulse_out = 1'b0;
    end
endgenerate

endmodule //end of com_edge_detect
`endif //end of com_edge_detect_v

