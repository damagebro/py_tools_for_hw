import axi_vip_pkg::*;

module axi_slave #(
    parameter int SLAVE_ID = 0,
    parameter int AXI_AW = 32,
    parameter int AXI_DW = 32,
    parameter int AXI_IDW = 4,
    parameter string CFG_FILE_DEFAULT = "../axi_vip.cfg"
)
(
    input logic clk,
    input logic rst_n,
    axi_interface.slave s_axi
);

localparam int AXI_SW = AXI_DW / 8;

typedef struct packed {
    logic [AXI_IDW-1:0] id;
    logic [1:0]         resp;
} b_item_t;

typedef struct packed {
    logic [AXI_IDW-1:0] id;
    logic [AXI_AW-1:0]  addr;
} aw_item_t;

typedef struct packed {
    logic [AXI_DW-1:0] data;
    logic [AXI_SW-1:0] strb;
    logic              last;
} w_item_t;

typedef struct packed {
    logic [AXI_IDW-1:0] id;
    logic [AXI_AW-1:0]  addr;
} ar_item_t;

string cfg_file;
string cfg_prefix;
string data_mode;
string data_file;
string awready_mode;
string perf_mode;
bit enable;
longint unsigned mem_size;
longint unsigned data_value;
int reorder_depth;
int awready_gap_min;
int awready_gap_max;
byte unsigned mem[];
b_item_t b_queue[$];
aw_item_t aw_queue[$];
w_item_t w_queue[$];
ar_item_t ar_queue[$];

initial begin
    if (!$value$plusargs("AXI_CFG=%s", cfg_file))
        cfg_file = CFG_FILE_DEFAULT;
    cfg_prefix = $sformatf("s%0d.", SLAVE_ID);
end

task automatic reset_bus();
    s_axi.awready <= 1'b0;
    s_axi.wready  <= 1'b0;
    s_axi.bid     <= '0;
    s_axi.bresp   <= '0;
    s_axi.bvalid  <= 1'b0;
    s_axi.arready <= 1'b0;
    s_axi.rid     <= '0;
    s_axi.rdata   <= '0;
    s_axi.rresp   <= '0;
    s_axi.rlast   <= 1'b0;
    s_axi.rvalid  <= 1'b0;
endtask

task automatic load_cfg();
    enable = cfg_get_bit(cfg_file, cfg_key(cfg_prefix, "enable"), 1'b1);
    mem_size = cfg_get_uint(cfg_file, cfg_key(cfg_prefix, "mem_size"), 4096);
    data_mode = cfg_get_string_default(cfg_file, cfg_key(cfg_prefix, "data_mode"), "addr");
    data_value = cfg_get_uint(cfg_file, cfg_key(cfg_prefix, "data_value"), 0);
    data_file = cfg_get_string_default(cfg_file, cfg_key(cfg_prefix, "data_file"), "");
    reorder_depth = cfg_get_int(
        cfg_file,
        cfg_key(cfg_prefix, "axi_reorder_depth"),
        cfg_get_int(
            cfg_file,
            cfg_key(cfg_prefix, "axi_reoder_depth"),
            cfg_get_int(cfg_file, cfg_key(cfg_prefix, "reorder_depth"), 0)
        )
    );
    awready_mode = cfg_get_string_default(
        cfg_file,
        cfg_key(cfg_prefix, "axi_awready_mode"),
        cfg_get_string_default(cfg_file, cfg_key(cfg_prefix, "awready_mode"), "continuous")
    );
    perf_mode = cfg_get_string_default(cfg_file, cfg_key(cfg_prefix, "axi_perf_mode"), "basic");
    awready_gap_min = cfg_get_int(
        cfg_file,
        cfg_key(cfg_prefix, "axi_awready_gap_min"),
        cfg_get_int(cfg_file, cfg_key(cfg_prefix, "awready_gap_min"), 0)
    );
    awready_gap_max = cfg_get_int(
        cfg_file,
        cfg_key(cfg_prefix, "axi_awready_gap_max"),
        cfg_get_int(cfg_file, cfg_key(cfg_prefix, "awready_gap_max"), 8)
    );
endtask

task automatic init_mem();
    int fd;
    int read_size;
    int byte_value;

    mem = new[int'(mem_size)];
    foreach (mem[idx]) begin
        if ((data_mode == "addr") || (data_mode == "data=addr"))
            mem[idx] = idx & 8'hff;
        else
            mem[idx] = data_value[idx % AXI_SW * 8 +: 8];
    end

    if ((data_mode == "file") && (data_file != "")) begin
        fd = $fopen(data_file, "rb");
        if (fd == 0) begin
            $display("[AXI_S%0d] warning: cannot open data_file=%s", SLAVE_ID, data_file);
        end else begin
            read_size = 0;
            foreach (mem[idx]) begin
                byte_value = $fgetc(fd);
                if (byte_value < 0)
                    break;
                mem[idx] = byte_value[7:0];
                read_size = read_size + 1;
            end
            $fclose(fd);
            $display("[AXI_S%0d] loaded %0d bytes from %s", SLAVE_ID, read_size, data_file);
        end
    end
endtask

task automatic wait_ready_gap();
    int gap_cycle;

    if (awready_mode != "random")
        return;

    gap_cycle = $urandom_range(awready_gap_max, awready_gap_min);
    repeat (gap_cycle)
        @(posedge clk);
endtask

task automatic write_mem(
    input longint unsigned addr,
    input logic [AXI_DW-1:0] data,
    input logic [AXI_SW-1:0] strb
);
    longint unsigned local_addr;

    local_addr = addr % mem_size;
    for (int idx = 0; idx < AXI_SW; idx++) begin
        if (strb[idx] && ((local_addr + idx) < mem_size))
            mem[local_addr + idx] = data[idx * 8 +: 8];
    end
endtask

function automatic logic [AXI_DW-1:0] read_mem(input longint unsigned addr);
    logic [AXI_DW-1:0] data;
    longint unsigned local_addr;

    data = '0;
    local_addr = addr % mem_size;
    for (int idx = 0; idx < AXI_SW; idx++) begin
        if ((local_addr + idx) < mem_size)
            data[idx * 8 +: 8] = mem[local_addr + idx];
    end
    return data;
endfunction

task automatic push_b(input logic [AXI_IDW-1:0] id, input logic [1:0] resp);
    b_item_t item;

    item.id = id;
    item.resp = resp;
    b_queue.push_back(item);
endtask

task automatic write_accept_thread();
    logic [AXI_IDW-1:0] id;
    logic [AXI_AW-1:0] addr;

    forever begin
        s_axi.awready <= 1'b0;
        s_axi.wready  <= 1'b0;
        wait_ready_gap();
        s_axi.awready <= enable;
        do @(posedge clk); while (!(enable && s_axi.awvalid && s_axi.awready));
        id = s_axi.awid;
        addr = s_axi.awaddr;
        s_axi.awready <= 1'b0;

        s_axi.wready <= 1'b1;
        do @(posedge clk); while (!(s_axi.wvalid && s_axi.wready));
        write_mem(addr, s_axi.wdata, s_axi.wstrb);
        s_axi.wready <= 1'b0;
        push_b(id, 2'b00);
    end
endtask

task automatic write_accept_fullperf_thread();
    aw_item_t aw_item;
    w_item_t w_item;
    b_item_t b_item;
    int rsp_index;
    int max_index;

    s_axi.awready <= enable;
    s_axi.wready  <= enable;
    forever begin
        @(posedge clk);
        if (enable && s_axi.awvalid && s_axi.awready) begin
            aw_item.id = s_axi.awid;
            aw_item.addr = s_axi.awaddr;
            aw_queue.push_back(aw_item);
        end
        if (enable && s_axi.wvalid && s_axi.wready) begin
            w_item.data = s_axi.wdata;
            w_item.strb = s_axi.wstrb;
            w_item.last = s_axi.wlast;
            w_queue.push_back(w_item);
        end
        if ((aw_queue.size() != 0) && (w_queue.size() != 0)) begin
            aw_item = aw_queue.pop_front();
            w_item = w_queue.pop_front();
            write_mem(aw_item.addr, w_item.data, w_item.strb);
            if (w_item.last)
                push_b(aw_item.id, 2'b00);
        end
        if (s_axi.bvalid && s_axi.bready)
            s_axi.bvalid <= 1'b0;
        if ((!s_axi.bvalid || s_axi.bready) && (b_queue.size() != 0)) begin
            if (reorder_depth <= 0) begin
                rsp_index = 0;
            end else begin
                max_index = b_queue.size() - 1;
                if (max_index >= reorder_depth)
                    max_index = reorder_depth - 1;
                rsp_index = $urandom_range(max_index, 0);
            end
            b_item = b_queue[rsp_index];
            b_queue.delete(rsp_index);
            s_axi.bid    <= b_item.id;
            s_axi.bresp  <= b_item.resp;
            s_axi.bvalid <= 1'b1;
        end
    end
endtask

task automatic b_response_thread();
    int rsp_index;
    int max_index;
    b_item_t item;

    forever begin
        wait (b_queue.size() > 0);
        if (reorder_depth <= 0) begin
            rsp_index = 0;
        end else begin
            max_index = b_queue.size() - 1;
            if (max_index >= reorder_depth)
                max_index = reorder_depth - 1;
            rsp_index = $urandom_range(max_index, 0);
        end

        item = b_queue[rsp_index];
        b_queue.delete(rsp_index);
        s_axi.bid    <= item.id;
        s_axi.bresp  <= item.resp;
        s_axi.bvalid <= 1'b1;
        do @(posedge clk); while (!s_axi.bready);
        s_axi.bvalid <= 1'b0;
        @(posedge clk);
    end
endtask

task automatic read_thread();
    forever begin
        s_axi.arready <= enable;
        do @(posedge clk); while (!(enable && s_axi.arvalid && s_axi.arready));
        s_axi.arready <= 1'b0;
        s_axi.rid     <= s_axi.arid;
        s_axi.rdata   <= read_mem(s_axi.araddr);
        s_axi.rresp   <= 2'b00;
        s_axi.rlast   <= 1'b1;
        s_axi.rvalid  <= 1'b1;
        do @(posedge clk); while (!s_axi.rready);
        s_axi.rvalid <= 1'b0;
        s_axi.rlast  <= 1'b0;
        @(posedge clk);
    end
endtask

task automatic read_fullperf_thread();
    ar_item_t ar_item;

    s_axi.arready <= enable;
    forever begin
        @(posedge clk);
        if (enable && s_axi.arvalid && s_axi.arready) begin
            ar_item.id = s_axi.arid;
            ar_item.addr = s_axi.araddr;
            ar_queue.push_back(ar_item);
        end
        if (s_axi.rvalid && s_axi.rready) begin
            s_axi.rvalid <= 1'b0;
            s_axi.rlast  <= 1'b0;
        end
        if ((!s_axi.rvalid || s_axi.rready) && (ar_queue.size() != 0)) begin
            ar_item = ar_queue.pop_front();
            s_axi.rid    <= ar_item.id;
            s_axi.rdata  <= read_mem(ar_item.addr);
            s_axi.rresp  <= 2'b00;
            s_axi.rlast  <= 1'b1;
            s_axi.rvalid <= 1'b1;
        end
    end
endtask

initial begin
    reset_bus();
    @(posedge rst_n);
    @(posedge clk);
    load_cfg();
    init_mem();
    if (!enable)
        $display("[AXI_S%0d] disabled", SLAVE_ID);
    else
        $display("[AXI_S%0d] enabled mem_size=0x%0h reorder_depth=%0d", SLAVE_ID, mem_size, reorder_depth);
    if (perf_mode == "full") begin
        fork
            write_accept_fullperf_thread();
            read_fullperf_thread();
        join_none
    end else begin
        fork
            write_accept_thread();
            b_response_thread();
            read_thread();
        join_none
    end
end

endmodule
