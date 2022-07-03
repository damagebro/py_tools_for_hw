str_head = '''\
/******************************************************************************
*
*  Authors:   <author>
*    Email:   <email>
*     Date:   <date>
*
*  Description:
*  -
*
*  Modify:
*  -
*
******************************************************************************/\
'''

str_module = '''\
`ifndef <MODULE_NAME>_v
`define <MODULE_NAME>_v
module <MODULE_NAME> #( parameter
<parm_list>
)
(
<port_list>
);
//localparam-----------------------------------------------------------------
//reg  declare---------------------------------------------------------------
//wire declare---------------------------------------------------------------
//statement------------------------------------------------------------------

endmodule //end of <MODULE_NAME>
`endif //end of <MODULE_NAME>_v\
'''