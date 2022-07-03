program automatic apb_test( ApbTbIf.tx apb_if );

ApbEnv cApbEnv;
initial begin
    cApbEnv = new( apb_if );
    cApbEnv.build();
    cApbEnv.run();
end

endprogram:apb_test