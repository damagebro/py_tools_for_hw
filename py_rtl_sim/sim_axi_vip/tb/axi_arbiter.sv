module axi_arbiter #(
    parameter int MASTER_NUM = 1,
    parameter int AXI_AW = 32,
    parameter int AXI_DW = 32,
    parameter int AXI_IDW = 4
)(
    input wire clk,
    input wire rst_n,
    axi_interface.slave s_axi [MASTER_NUM],
    axi_interface.master m_axi
);

localparam int SEL_W = (MASTER_NUM > 1) ? $clog2(MASTER_NUM) : 1;

logic                 r_wr_active;
logic [SEL_W-1:0]     r_wr_sel;
logic                 r_rd_active;
logic [SEL_W-1:0]     r_rd_sel;
int unsigned          r_aw_rr_next;
int unsigned          r_ar_rr_next;
logic                 b_aw_found;
logic [SEL_W-1:0]     w_aw_sel;
logic                 b_b_found;
logic [SEL_W-1:0]     w_b_sel;
logic                 b_ar_found;
logic [SEL_W-1:0]     w_ar_sel;
logic                 b_aw_fire;
logic                 b_w_fire;
logic                 b_ar_fire;
logic                 b_r_fire;

initial begin
    if (MASTER_NUM > (1 << AXI_IDW))
        $fatal(1, "[AXI_ARB] MASTER_NUM must not exceed AXI ID capacity");
end

always_comb begin
    int unsigned candidate;

    b_aw_found = 1'b0;
    w_aw_sel = '0;
    b_b_found = m_axi.bvalid && (m_axi.bid < MASTER_NUM);
    w_b_sel = m_axi.bid[SEL_W-1:0];
    b_ar_found = 1'b0;
    w_ar_sel = '0;

    for (int offset = 0; offset < MASTER_NUM; offset++) begin
        candidate = r_aw_rr_next + offset;
        if (candidate >= MASTER_NUM)
            candidate = candidate - MASTER_NUM;
        if (!b_aw_found && s_axi[candidate].awvalid) begin
            b_aw_found = 1'b1;
            w_aw_sel = candidate[SEL_W-1:0];
        end
    end

    for (int offset = 0; offset < MASTER_NUM; offset++) begin
        candidate = r_ar_rr_next + offset;
        if (candidate >= MASTER_NUM)
            candidate = candidate - MASTER_NUM;
        if (!b_ar_found && s_axi[candidate].arvalid) begin
            b_ar_found = 1'b1;
            w_ar_sel = candidate[SEL_W-1:0];
        end
    end
end

always_comb begin
    m_axi.awid = '0;
    m_axi.awaddr = '0;
    m_axi.awlen = '0;
    m_axi.awsize = '0;
    m_axi.awburst = '0;
    m_axi.awvalid = 1'b0;
    m_axi.wdata = '0;
    m_axi.wstrb = '0;
    m_axi.wlast = 1'b0;
    m_axi.wvalid = 1'b0;
    m_axi.bready = 1'b0;
    m_axi.arid = '0;
    m_axi.araddr = '0;
    m_axi.arlen = '0;
    m_axi.arsize = '0;
    m_axi.arburst = '0;
    m_axi.arvalid = 1'b0;
    m_axi.rready = 1'b0;

    for (int idx = 0; idx < MASTER_NUM; idx++) begin
        s_axi[idx].awready = 1'b0;
        s_axi[idx].wready = 1'b0;
        s_axi[idx].bid = '0;
        s_axi[idx].bresp = '0;
        s_axi[idx].bvalid = 1'b0;
        s_axi[idx].arready = 1'b0;
        s_axi[idx].rid = '0;
        s_axi[idx].rdata = '0;
        s_axi[idx].rresp = '0;
        s_axi[idx].rlast = 1'b0;
        s_axi[idx].rvalid = 1'b0;
    end

    if (!r_wr_active && b_aw_found) begin
        m_axi.awid = s_axi[w_aw_sel].awid;
        m_axi.awaddr = s_axi[w_aw_sel].awaddr;
        m_axi.awlen = s_axi[w_aw_sel].awlen;
        m_axi.awsize = s_axi[w_aw_sel].awsize;
        m_axi.awburst = s_axi[w_aw_sel].awburst;
        m_axi.awvalid = s_axi[w_aw_sel].awvalid;
        s_axi[w_aw_sel].awready = m_axi.awready;
    end

    if (r_wr_active) begin
        m_axi.wdata = s_axi[r_wr_sel].wdata;
        m_axi.wstrb = s_axi[r_wr_sel].wstrb;
        m_axi.wlast = s_axi[r_wr_sel].wlast;
        m_axi.wvalid = s_axi[r_wr_sel].wvalid;
        s_axi[r_wr_sel].wready = m_axi.wready;
    end

    if (b_b_found) begin
        s_axi[w_b_sel].bid = m_axi.bid;
        s_axi[w_b_sel].bresp = m_axi.bresp;
        s_axi[w_b_sel].bvalid = m_axi.bvalid;
        m_axi.bready = s_axi[w_b_sel].bready;
    end

    if (!r_rd_active && b_ar_found) begin
        m_axi.arid = s_axi[w_ar_sel].arid;
        m_axi.araddr = s_axi[w_ar_sel].araddr;
        m_axi.arlen = s_axi[w_ar_sel].arlen;
        m_axi.arsize = s_axi[w_ar_sel].arsize;
        m_axi.arburst = s_axi[w_ar_sel].arburst;
        m_axi.arvalid = s_axi[w_ar_sel].arvalid;
        s_axi[w_ar_sel].arready = m_axi.arready;
    end

    if (r_rd_active) begin
        s_axi[r_rd_sel].rid = m_axi.rid;
        s_axi[r_rd_sel].rdata = m_axi.rdata;
        s_axi[r_rd_sel].rresp = m_axi.rresp;
        s_axi[r_rd_sel].rlast = m_axi.rlast;
        s_axi[r_rd_sel].rvalid = m_axi.rvalid;
        m_axi.rready = s_axi[r_rd_sel].rready;
    end
end

assign b_aw_fire = !r_wr_active && b_aw_found && m_axi.awready;
assign b_w_fire = r_wr_active && m_axi.wvalid && m_axi.wready && m_axi.wlast;
assign b_ar_fire = !r_rd_active && b_ar_found && m_axi.arready;
assign b_r_fire = r_rd_active && m_axi.rvalid && m_axi.rlast && s_axi[r_rd_sel].rready;

always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        r_wr_active <= 1'b0;
        r_wr_sel <= '0;
        r_rd_active <= 1'b0;
        r_rd_sel <= '0;
        r_aw_rr_next <= '0;
        r_ar_rr_next <= '0;
    end else begin
        if (b_w_fire) begin
            r_wr_active <= 1'b0;
        end else if (b_aw_fire) begin
            r_wr_active <= 1'b1;
            r_wr_sel <= w_aw_sel;
            if (w_aw_sel == MASTER_NUM - 1)
                r_aw_rr_next <= '0;
            else
                r_aw_rr_next <= w_aw_sel + 1'b1;
        end

        if (b_r_fire) begin
            r_rd_active <= 1'b0;
        end else if (b_ar_fire) begin
            r_rd_active <= 1'b1;
            r_rd_sel <= w_ar_sel;
            if (w_ar_sel == MASTER_NUM - 1)
                r_ar_rr_next <= '0;
            else
                r_ar_rr_next <= w_ar_sel + 1'b1;
        end
    end
end

endmodule
