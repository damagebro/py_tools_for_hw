import axi_vip_pkg::*;

module axi_master #(
    parameter int MASTER_ID = 0,
    parameter int AXI_AW = 32,
    parameter int AXI_DW = 32,
    parameter int AXI_IDW = 4,
    parameter string CFG_FILE_DEFAULT = "../axi_vip.cfg"
)
(
    input  wire clk,
    input  wire rst_n,
    output reg  done,
    axi_interface.master m_axi
);

localparam int AXI_SW = AXI_DW / 8;

string cfg_file;
string cfg_prefix;
string data_mode;
string data_file;
string awvalid_mode;
bit enable;
longint unsigned base_addr;
longint unsigned byte_size;
longint unsigned data_value;
int awvalid_gap_min;
int awvalid_gap_max;
int master_num;
byte unsigned file_data[];
int file_size;

initial begin
    if (!$value$plusargs("AXI_CFG=%s", cfg_file))
        cfg_file = CFG_FILE_DEFAULT;
    cfg_prefix = $sformatf("m%0d.", MASTER_ID);
end

task automatic reset_bus();
    m_axi.awid    <= '0;
    m_axi.awaddr  <= '0;
    m_axi.awlen   <= '0;
    m_axi.awsize  <= clog2_bytes(AXI_SW);
    m_axi.awburst <= 2'b01;
    m_axi.awvalid <= 1'b0;
    m_axi.wdata   <= '0;
    m_axi.wstrb   <= '0;
    m_axi.wlast   <= 1'b0;
    m_axi.wvalid  <= 1'b0;
    m_axi.bready  <= 1'b0;
    m_axi.arid    <= '0;
    m_axi.araddr  <= '0;
    m_axi.arlen   <= '0;
    m_axi.arsize  <= clog2_bytes(AXI_SW);
    m_axi.arburst <= 2'b01;
    m_axi.arvalid <= 1'b0;
    m_axi.rready  <= 1'b0;
endtask

task automatic load_cfg();
    master_num = cfg_get_int(cfg_file, "master_num", 1);
    enable = cfg_get_bit(cfg_file, cfg_key(cfg_prefix, "enable"), MASTER_ID < master_num);
    base_addr = cfg_get_uint(cfg_file, cfg_key(cfg_prefix, "base_addr"), 32'h0000_1000);
    byte_size = cfg_get_uint(cfg_file, cfg_key(cfg_prefix, "byte_size"), AXI_SW);
    data_mode = cfg_get_string_default(cfg_file, cfg_key(cfg_prefix, "data_mode"), "addr");
    data_value = cfg_get_uint(cfg_file, cfg_key(cfg_prefix, "data_value"), 0);
    data_file = cfg_get_string_default(cfg_file, cfg_key(cfg_prefix, "data_file"), "");
    awvalid_mode = cfg_get_string_default(
        cfg_file,
        cfg_key(cfg_prefix, "axi_awvalid_mode"),
        cfg_get_string_default(cfg_file, cfg_key(cfg_prefix, "awvalid_mode"), "continuous")
    );
    awvalid_gap_min = cfg_get_int(
        cfg_file,
        cfg_key(cfg_prefix, "axi_awvalid_gap_min"),
        cfg_get_int(cfg_file, cfg_key(cfg_prefix, "awvalid_gap_min"), 0)
    );
    awvalid_gap_max = cfg_get_int(
        cfg_file,
        cfg_key(cfg_prefix, "axi_awvalid_gap_max"),
        cfg_get_int(cfg_file, cfg_key(cfg_prefix, "awvalid_gap_max"), 8)
    );
endtask

task automatic load_file_data();
    int fd;

    file_size = 0;
    if ((data_mode != "file") || (data_file == ""))
        return;

    file_data = new[int'(byte_size)];
    fd = $fopen(data_file, "rb");
    if (fd == 0) begin
        $display("[AXI_M%0d] warning: cannot open data_file=%s", MASTER_ID, data_file);
        return;
    end
    file_size = $fread(file_data, fd);
    $fclose(fd);
    $display("[AXI_M%0d] loaded %0d bytes from %s", MASTER_ID, file_size, data_file);
endtask

function automatic logic [AXI_DW-1:0] build_data(
    input longint unsigned addr,
    input int byte_offset
);
    logic [AXI_DW-1:0] data;

    data = '0;
    for (int idx = 0; idx < AXI_SW; idx++) begin
        if ((data_mode == "addr") || (data_mode == "data=addr")) begin
            data[idx * 8 +: 8] = (addr + idx) & 8'hff;
        end else if (data_mode == "file") begin
            if ((byte_offset + idx) < file_size)
                data[idx * 8 +: 8] = file_data[byte_offset + idx];
        end else begin
            data[idx * 8 +: 8] = data_value[idx * 8 +: 8];
        end
    end
    return data;
endfunction

task automatic wait_awvalid_gap();
    int gap_cycle;

    if (awvalid_mode != "random")
        return;

    gap_cycle = $urandom_range(awvalid_gap_max, awvalid_gap_min);
    repeat (gap_cycle)
        @(posedge clk);
endtask

task automatic axi_write_one(
    input longint unsigned addr,
    input logic [AXI_DW-1:0] data
);
    wait_awvalid_gap();

    m_axi.awid    <= AXI_IDW'(MASTER_ID);
    m_axi.awaddr  <= AXI_AW'(addr);
    m_axi.awlen   <= 8'h00;
    m_axi.awsize  <= clog2_bytes(AXI_SW);
    m_axi.awburst <= 2'b01;
    m_axi.awvalid <= 1'b1;
    do @(posedge clk); while (!m_axi.awready);
    m_axi.awvalid <= 1'b0;

    m_axi.wdata  <= data;
    m_axi.wstrb  <= '1;
    m_axi.wlast  <= 1'b1;
    m_axi.wvalid <= 1'b1;
    do @(posedge clk); while (!m_axi.wready);
    m_axi.wvalid <= 1'b0;
    m_axi.wlast  <= 1'b0;

    m_axi.bready <= 1'b1;
    do @(posedge clk); while (!m_axi.bvalid);
    if (m_axi.bresp != 2'b00)
        $display("[AXI_M%0d] write response error addr=0x%0h bresp=%0h", MASTER_ID, addr, m_axi.bresp);
    @(posedge clk);
    m_axi.bready <= 1'b0;
endtask

initial begin
    done = 1'b0;
    reset_bus();
    @(posedge rst_n);
    @(posedge clk);

    load_cfg();
    if (!enable) begin
        done = 1'b1;
        $display("[AXI_M%0d] disabled", MASTER_ID);
    end else begin
        load_file_data();
        $display("[AXI_M%0d] start base=0x%0h bytes=0x%0h mode=%s", MASTER_ID, base_addr, byte_size, data_mode);
        for (int offset = 0; offset < byte_size; offset += AXI_SW) begin
            axi_write_one(base_addr + offset, build_data(base_addr + offset, offset));
        end
        done = 1'b1;
        $display("[AXI_M%0d] done", MASTER_ID);
    end
end

endmodule
