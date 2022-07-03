//--------------------------------------------------------------------------------
//Default parameters.
//--------------------------------------------------------------------------------
`ifndef COM_SYNC_STAGE
    `define COM_SYNC_STAGE 3
`endif

`ifndef COM_SYS_W
    `define COM_SYS_W 4
`endif

`define COM_DFT_IF input wire [`COM_SYS_W-1:0]
`define COM_SYS_IF input wire [`COM_SYS_W-1:0]

//--------------------------------------------------------------------------------
//FUNCTION DEFINE
//--------------------------------------------------------------------------------
//`define COM_MAX(a, b) ((a) > (b) ? (a) : (b))
//`define COM_MIN(a, b) ((a) < (b) ? (a) : (b))

//--------------------------------------------------------------------------------
//report&assert define
//--------------------------------------------------------------------------------
`define COM_PARAM_ASSERT( cond, estr )                               \
`ifdef COM_ASSERT_ON                                                 \
    initial begin                                                    \
        assert(cond) else $fatal("Com Parameter Error: '%s'",estr);  \
    end                                                              \
`else                                                                \
/*empty statement for lint;*/                                        \
`endif                                                               \

`define COM_SIGNAL_ASSERT( str_property, clk,rst_n, key,cond,estr )  \
`ifdef COM_ASSERT_ON                                                 \
    str_property: assert property (                                  \
        @(posedge clk) disable iff (!rst_n) key |-> (cond)           \
    ) else begin #100; $fatal("Com Signal Error: '%s'",estr); end    \
`else                                                                \
/*empty statement for lint;*/                                        \
`endif

`define COM_SIGNAL_ASSERT_LITE( str_property, key,cond,estr )        \
`ifdef COM_ASSERT_ON                                                 \
    str_property: assert property (                                  \
        @(posedge clk) disable iff (!rst_n) key |-> (cond)           \
    ) else begin #100; $fatal("Com Signal Error: '%s'",estr); end    \
`else                                                                \
/*empty statement for lint;*/                                        \
`endif
