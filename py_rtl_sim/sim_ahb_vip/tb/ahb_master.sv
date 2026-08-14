import ahb_vip_pkg::*;

module ahb_master #(
    parameter int MASTER_ID = 0,
    parameter int AHB_AW = 32,
    parameter int AHB_DW = 32,
    parameter string CFG_FILE_DEFAULT = "../ahb_vip.cfg"
)(
    input  logic clk,
    input  logic rst_n,
    output logic done,
    ahb_interface.master m_ahb
);

localparam int AHB_SW = AHB_DW / 8;

typedef struct {
    longint unsigned  addr;
    logic [AHB_DW-1:0] data;
} txt_item_t;

string cfg_file;
string cfg_prefix;
string rw_mode;
string data_mode;
string data_file;
bit enable;
bit performance_mode;
longint unsigned base_addr;
longint unsigned byte_size;
longint unsigned data_value;
longint unsigned hsize_cfg;
byte unsigned file_data[];
txt_item_t txt_items[$];
int file_size;
int read_error_cnt;

initial begin
    if (!$value$plusargs("AHB_CFG=%s", cfg_file))
        cfg_file = CFG_FILE_DEFAULT;
    cfg_prefix = $sformatf("m%0d.", MASTER_ID);
end

task automatic reset_bus();
    m_ahb.haddr  <= '0;
    m_ahb.htrans <= 2'b00;
    m_ahb.hwrite <= 1'b0;
    m_ahb.hsize  <= clog2_bytes(AHB_SW);
    m_ahb.hburst <= 3'b000;
    m_ahb.hprot  <= 4'b0011;
    m_ahb.hwdata <= '0;
endtask

task automatic load_cfg();
    enable = cfg_get_bit(cfg_file, {cfg_prefix, "enable"}, 1'b1);
    performance_mode = cfg_get_bit(cfg_file, {cfg_prefix, "performance_mode"}, 1'b0);
    base_addr = cfg_get_uint(cfg_file, {cfg_prefix, "base_addr"}, 32'h1000);
    byte_size = cfg_get_uint(cfg_file, {cfg_prefix, "byte_size"}, AHB_SW);
    rw_mode = cfg_get_string_default(cfg_file, {cfg_prefix, "rw_mode"}, "write");
    data_mode = cfg_get_string_default(cfg_file, {cfg_prefix, "data_mode"}, "addr");
    data_value = cfg_get_uint(cfg_file, {cfg_prefix, "data_value"}, 0);
    data_file = cfg_get_string_default(cfg_file, {cfg_prefix, "data_file"}, "");
    hsize_cfg = cfg_get_uint(cfg_file, {cfg_prefix, "hsize"}, clog2_bytes(AHB_SW));
endtask

task automatic load_file_data();
    int fd;
    int byte_value;

    file_size = 0;
    if ((data_mode == "txt") || (data_mode == "text")) begin
        load_txt_data();
        return;
    end
    if ((data_mode != "file") || (data_file == ""))
        return;
    file_data = new[int'(byte_size)];
    fd = $fopen(data_file, "rb");
    if (fd == 0) begin
        $display("[AHB_M%0d] warning: cannot open data_file=%s", MASTER_ID, data_file);
        return;
    end
    for (int idx = 0; idx < int'(byte_size); idx++) begin
        byte_value = $fgetc(fd);
        if (byte_value < 0)
            break;
        file_data[idx] = byte_value[7:0];
        file_size = file_size + 1;
    end
    $fclose(fd);
    $display("[AHB_M%0d] loaded %0d bytes from %s", MASTER_ID, file_size, data_file);
endtask

task automatic append_txt_token(
    input string token,
    inout bit expect_addr,
    inout string addr_token
);
    txt_item_t item;

    if (expect_addr) begin
        addr_token = token;
        expect_addr = 1'b0;
    end else begin
        item.addr = str_to_uint(addr_token);
        item.data = AHB_DW'(str_to_uint(token));
        txt_items.push_back(item);
        expect_addr = 1'b1;
    end
endtask

task automatic load_txt_data();
    int fd;
    int token_start;
    string line;
    string token;
    string addr_token;
    bit expect_addr;

    txt_items.delete();
    if (data_file == "") begin
        $display("[AHB_M%0d] warning: txt mode needs data_file", MASTER_ID);
        return;
    end

    fd = $fopen(data_file, "r");
    if (fd == 0) begin
        $display("[AHB_M%0d] warning: cannot open data_file=%s", MASTER_ID, data_file);
        return;
    end

    expect_addr = 1'b1;
    while (!$feof(fd)) begin
        void'($fgets(line, fd));
        line = strip_comment(line);
        token_start = 0;
        for (int char_idx = 0; char_idx < line.len(); char_idx++) begin
            if (is_space(line.getc(char_idx))) begin
                if (char_idx > token_start) begin
                    token = line.substr(token_start, char_idx - 1);
                    append_txt_token(token, expect_addr, addr_token);
                end
                token_start = char_idx + 1;
            end
        end
        if (line.len() > token_start) begin
            token = line.substr(token_start, line.len() - 1);
            append_txt_token(token, expect_addr, addr_token);
        end
    end
    $fclose(fd);

    if (!expect_addr)
        $display("[AHB_M%0d] warning: ignored dangling addr token %s", MASTER_ID, addr_token);
    $display("[AHB_M%0d] loaded %0d text transactions from %s", MASTER_ID, txt_items.size(), data_file);
endtask

function automatic logic [AHB_DW-1:0] build_data(
    input longint unsigned addr,
    input int byte_offset
);
    logic [AHB_DW-1:0] data;

    data = '0;
    for (int idx = 0; idx < AHB_SW; idx++) begin
        if ((data_mode == "addr") || (data_mode == "data=addr"))
            data[idx * 8 +: 8] = (addr + idx) & 8'hff;
        else if ((data_mode == "file") && ((byte_offset + idx) < file_size))
            data[idx * 8 +: 8] = file_data[byte_offset + idx];
        else
            data[idx * 8 +: 8] = data_value[idx * 8 +: 8];
    end
    return data;
endfunction

task automatic ahb_transfer(
    input bit write_transfer,
    input longint unsigned addr,
    input logic [AHB_DW-1:0] write_data,
    input logic [AHB_DW-1:0] expected_data,
    input bit continue_transfer = 1'b0
);
    m_ahb.haddr  <= AHB_AW'(addr);
    m_ahb.htrans <= 2'b10;
    m_ahb.hwrite <= write_transfer;
    m_ahb.hsize  <= hsize_cfg;
    m_ahb.hburst <= 3'b000;
    m_ahb.hwdata <= write_data;
    do @(posedge clk); while (!m_ahb.hready);
    if (m_ahb.hresp != 2'b00)
        $display("[AHB_M%0d] transfer error addr=0x%0h hresp=%0h", MASTER_ID, addr, m_ahb.hresp);
    if (!write_transfer && (m_ahb.hrdata !== expected_data)) begin
        read_error_cnt = read_error_cnt + 1;
        $display("[AHB_M%0d] read mismatch addr=0x%0h exp=0x%0h act=0x%0h",
                 MASTER_ID, addr, expected_data, m_ahb.hrdata);
    end
    if (!continue_transfer) begin
        m_ahb.htrans <= 2'b00;
        m_ahb.hwrite <= 1'b0;
        @(posedge clk);
    end
endtask

initial begin
    done = 1'b0;
    read_error_cnt = 0;
    reset_bus();
    @(posedge rst_n);
    @(posedge clk);
    load_cfg();
    if (!enable) begin
        done = 1'b1;
        $display("[AHB_M%0d] disabled", MASTER_ID);
    end else begin
        load_file_data();
        if ((data_mode == "txt") || (data_mode == "text")) begin
            foreach (txt_items[idx])
                ahb_transfer(1'b1, txt_items[idx].addr, txt_items[idx].data, '0,
                             performance_mode && (idx != txt_items.size() - 1));
            foreach (txt_items[idx])
                ahb_transfer(1'b0, txt_items[idx].addr, '0, txt_items[idx].data);
        end else begin
            $display("[AHB_M%0d] start base=0x%0h bytes=0x%0h mode=%s", MASTER_ID, base_addr, byte_size, rw_mode);
            for (int offset = 0; offset < byte_size; offset += AHB_SW)
                ahb_transfer(1'b1, base_addr + offset,
                             build_data(base_addr + offset, offset), '0,
                             performance_mode && ((offset + AHB_SW) < byte_size));
            for (int offset = 0; offset < byte_size; offset += AHB_SW)
                ahb_transfer(1'b0, base_addr + offset, '0,
                             build_data(base_addr + offset, offset));
        end
        if (read_error_cnt != 0)
            $fatal(1, "[AHB_M%0d] read compare failed, error_count=%0d",
                   MASTER_ID, read_error_cnt);
        done = 1'b1;
        $display("[AHB_M%0d] done", MASTER_ID);
    end
end

endmodule
