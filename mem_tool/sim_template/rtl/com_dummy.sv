module com_dummy();

com_ecc_spram_shell    #( .DATA_W(128),.DEPTH(1024),.STRB_W(1),.MEM_USER(0) , .REQ_PIPE(0),.RSP_PIPE(0)/*,.ECC_DW(DATA_W)*/ ) u_com_ecc_spram_shell_1();
com_ecc_spram_shell    #( .DATA_W(128),.DEPTH(1024),.STRB_W(2),.MEM_USER(0) , .REQ_PIPE(0),.RSP_PIPE(0)/*,.ECC_DW(DATA_W)*/ ) u_com_ecc_spram_shell_2();
com_ecc_spram_shell    #( .DATA_W(128),.DEPTH(1024),.STRB_W(2),.MEM_USER(1) , .REQ_PIPE(0),.RSP_PIPE(0),.ECC_DW(64)     )     u_com_ecc_spram_shell_3();
com_ecc_spram_shell    #( .DATA_W(100),.DEPTH(200 ),.STRB_W(2),.MEM_USER(10), .REQ_PIPE(0),.RSP_PIPE(0),.ECC_DW(25)     )     u_com_ecc_spram_shell_4();
com_ecc_tpram1ck_shell #( .DATA_W(128),.DEPTH(600),.STRB_W(1),.MEM_USER(0)  , .REQ_PIPE(0),.RSP_PIPE(0)/*,.ECC_DW(DATA_W)*/ ) u_com_ecc_tpram1ck_shell_1();
com_ecc_tpram1ck_shell #( .DATA_W(128),.DEPTH(200),.STRB_W(4),.MEM_USER(10) , .REQ_PIPE(0),.RSP_PIPE(0)/*,.ECC_DW(DATA_W)*/ ) u_com_ecc_tpram1ck_shell_2();
com_ecc_tpram2ck_shell #( .DATA_W(128),.DEPTH(512),.STRB_W(1),.MEM_USER(0)  , .REQ_PIPE(0),.RSP_PIPE(0)/*,.ECC_DW(DATA_W)*/ ) u_com_ecc_tpram2ck_shell_1();

com_spram_shell    #( .DATA_W(128),.DEPTH(1024),.STRB_W(1),.MEM_USER(0)  ) u_com_spram_shell_1();
com_spram_shell    #( .DATA_W(128),.DEPTH(1024),.STRB_W(2),.MEM_USER(0)  ) u_com_spram_shell_2();
com_spram_shell    #( .DATA_W(128),.DEPTH(1024),.STRB_W(2),.MEM_USER(1)  ) u_com_spram_shell_3();
com_spram_shell    #( .DATA_W(100),.DEPTH(200 ),.STRB_W(2),.MEM_USER(10) ) u_com_spram_shell_4();
com_tpram1ck_shell #( .DATA_W(128),.DEPTH(600),.STRB_W(1),.MEM_USER(0)   ) u_com_tpram1ck_shell_1();
com_tpram1ck_shell #( .DATA_W(128),.DEPTH(200),.STRB_W(4),.MEM_USER(10)  ) u_com_tpram1ck_shell_2();
com_tpram2ck_shell #( .DATA_W(128),.DEPTH(512),.STRB_W(1),.MEM_USER(0)   ) u_com_tpram2ck_shell_1();

com_sprom_mannul #( .DATA_W(30),.DEPTH(120),.MEM_USER(0) ) u_com_sprom_mannul();

endmodule
