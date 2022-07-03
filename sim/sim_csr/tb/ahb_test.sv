program automatic ahb_test( AhbTbIf.tx ahb_if );

AhbEnv cAhbEnv;
initial begin
    cAhbEnv = new( ahb_if );
    cAhbEnv.build();
    cAhbEnv.run();
end

endprogram:ahb_test