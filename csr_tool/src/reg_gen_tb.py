from __future__ import annotations

from pathlib import Path

from .models import FieldModel, ModuleModel, RegisterModel
from .reg_common import clog2, write_text


def generate_tb(module: ModuleModel, out_dir: str) -> list[Path]:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    seen: set[str] = set()
    for item, _, _ in module.walk():
        source = str(Path(item.source_path).resolve()).lower()
        if source in seen:
            continue
        seen.add(source)
        tb_path = output / f"{item.name}_tb.sv"
        ral_path = output / f"{item.name}_ral_pkg.sv"
        write_text(tb_path, _testbench(item))
        write_text(ral_path, _ral_package(item))
        generated.extend([tb_path, ral_path])
    return generated


def _testbench(module: ModuleModel) -> str:
    targets = [
        reg for reg in module.registers if reg.reg_type in {"slave", "mem"}
    ]
    deep = max(
        (reg.special.shadow for reg in module.registers),
        default=0,
    )
    declarations = [
        "localparam integer CSR_AW = 32;",
        f"localparam integer CSR_DW = {module.base_info.reg_bitwidth};",
        "reg clk;",
        "reg rst_n;",
        "reg i_csr_req_write;",
        "reg [CSR_AW-1:0] i_csr_req_addr;",
        "reg [CSR_DW-1:0] i_csr_req_wdata;",
        "reg [CSR_DW/8-1:0] i_csr_req_wstrb;",
        "reg i_csr_req_valid;",
        "wire o_csr_req_ready;",
        "wire [CSR_DW-1:0] o_csr_rsp_rdata;",
        "wire o_csr_rsp_rvalid;",
    ]
    connections = [
        ".clk (clk)",
        ".rst_n (rst_n)",
        ".i_csr_req_write (i_csr_req_write)",
        ".i_csr_req_addr (i_csr_req_addr)",
        ".i_csr_req_wdata (i_csr_req_wdata)",
        ".i_csr_req_wstrb (i_csr_req_wstrb)",
        ".i_csr_req_valid (i_csr_req_valid)",
        ".o_csr_req_ready (o_csr_req_ready)",
        ".o_csr_rsp_rdata (o_csr_rsp_rdata)",
        ".o_csr_rsp_rvalid (o_csr_rsp_rvalid)",
    ]
    input_initializers: list[str] = []
    for reg in module.registers:
        for field in reg.fields:
            dims = _dims(reg, field)
            tag = f"{reg.name}_{field.name}"
            if reg.reg_type == "cfg":
                declarations.append(f"wire {dims} o_cfg_{tag};")
                connections.append(f".o_cfg_{tag} (o_cfg_{tag})")
            elif reg.reg_type == "status":
                declarations.append(f"reg {dims} i_sta_{tag};")
                connections.append(f".i_sta_{tag} (i_sta_{tag})")
                input_initializers.append(f"    i_sta_{tag} = '0;")
            elif reg.reg_type == "cmd":
                declarations.append(f"wire {dims} o_cmd_{tag};")
                connections.append(f".o_cmd_{tag} (o_cmd_{tag})")
            elif reg.reg_type == "irq":
                declarations.append(f"reg {dims} i_irqsta_{tag};")
                declarations.append(f"wire {dims} o_irqclr_{tag};")
                connections.append(f".i_irqsta_{tag} (i_irqsta_{tag})")
                connections.append(f".o_irqclr_{tag} (o_irqclr_{tag})")
                input_initializers.append(f"    i_irqsta_{tag} = '0;")
    if any(reg.special.shadow for reg in module.registers):
        declarations.append("reg i_pulse_shadow_upen;")
        connections.append(".i_pulse_shadow_upen (i_pulse_shadow_upen)")
        input_initializers.append("    i_pulse_shadow_upen = 1'b0;")
    if deep >= 2:
        declarations.extend([
            "reg i_pulse_shadow_rden;",
            f"wire [{clog2(deep) - 1}:0] o_dbg_shadow_wr_idx;",
            f"wire [{clog2(deep) - 1}:0] o_dbg_shadow_rd_idx;",
            f"wire [{clog2(deep + 1) - 1}:0] o_dbg_shadow_water_level;",
            "wire o_pulse_err_write_when_full;",
            "wire o_pulse_err_read_when_empty;",
        ])
        connections.extend([
            ".i_pulse_shadow_rden (i_pulse_shadow_rden)",
            ".o_dbg_shadow_wr_idx (o_dbg_shadow_wr_idx)",
            ".o_dbg_shadow_rd_idx (o_dbg_shadow_rd_idx)",
            ".o_dbg_shadow_water_level (o_dbg_shadow_water_level)",
            ".o_pulse_err_write_when_full (o_pulse_err_write_when_full)",
            ".o_pulse_err_read_when_empty (o_pulse_err_read_when_empty)",
        ])
        input_initializers.append("    i_pulse_shadow_rden = 1'b0;")
    if targets:
        count = len(targets)
        declarations.extend([
            f"wire [{count - 1}:0] o_tx_csr_req_write;",
            f"wire [{count - 1}:0][CSR_AW-1:0] o_tx_csr_req_addr;",
            f"wire [{count - 1}:0][CSR_DW-1:0] o_tx_csr_req_wdata;",
            f"wire [{count - 1}:0][CSR_DW/8-1:0] o_tx_csr_req_wstrb;",
            f"wire [{count - 1}:0] o_tx_csr_req_valid;",
            f"reg [{count - 1}:0] i_tx_csr_req_ready;",
            f"reg [{count - 1}:0][CSR_DW-1:0] i_tx_csr_rsp_rdata;",
            f"reg [{count - 1}:0] i_tx_csr_rsp_rvalid;",
        ])
        connections.extend([
            ".o_tx_csr_req_write (o_tx_csr_req_write)",
            ".o_tx_csr_req_addr (o_tx_csr_req_addr)",
            ".o_tx_csr_req_wdata (o_tx_csr_req_wdata)",
            ".o_tx_csr_req_wstrb (o_tx_csr_req_wstrb)",
            ".o_tx_csr_req_valid (o_tx_csr_req_valid)",
            ".i_tx_csr_req_ready (i_tx_csr_req_ready)",
            ".i_tx_csr_rsp_rdata (i_tx_csr_rsp_rdata)",
            ".i_tx_csr_rsp_rvalid (i_tx_csr_rsp_rvalid)",
        ])
        input_initializers.extend([
            "    i_tx_csr_req_ready = '1;",
            "    i_tx_csr_rsp_rdata = '0;",
            "    i_tx_csr_rsp_rvalid = '0;",
        ])
    formatted = [
        f"    {item}{',' if index < len(connections) - 1 else ''}"
        for index, item in enumerate(connections)
    ]
    checks = _basic_checks(module)
    return "\n".join([
        "// Generated smoke test for CSR read and write behavior.",
        "`timescale 1ns/1ps",
        "",
        f"module {module.name}_tb;",
        "",
        *declarations,
        "reg [CSR_DW-1:0] r_read_data;",
        "",
        "always #5 clk = ~clk;",
        "",
        "task csr_write;",
        "    input [CSR_AW-1:0] addr;",
        "    input [CSR_DW-1:0] data;",
        "    begin",
        "        @(posedge clk);",
        "        i_csr_req_write <= 1'b1;",
        "        i_csr_req_addr <= addr;",
        "        i_csr_req_wdata <= data;",
        "        i_csr_req_wstrb <= '1;",
        "        i_csr_req_valid <= 1'b1;",
        "        do @(posedge clk); while (!o_csr_req_ready);",
        "        i_csr_req_valid <= 1'b0;",
        "    end",
        "endtask",
        "",
        "task csr_read;",
        "    input [CSR_AW-1:0] addr;",
        "    output [CSR_DW-1:0] data;",
        "    begin",
        "        @(posedge clk);",
        "        i_csr_req_write <= 1'b0;",
        "        i_csr_req_addr <= addr;",
        "        i_csr_req_valid <= 1'b1;",
        "        do @(posedge clk); while (!o_csr_req_ready);",
        "        i_csr_req_valid <= 1'b0;",
        "        do @(posedge clk); while (!o_csr_rsp_rvalid);",
        "        data = o_csr_rsp_rdata;",
        "    end",
        "endtask",
        "",
        "initial begin",
        "    clk = 1'b0;",
        "    rst_n = 1'b0;",
        "    i_csr_req_write = 1'b0;",
        "    i_csr_req_addr = '0;",
        "    i_csr_req_wdata = '0;",
        "    i_csr_req_wstrb = '0;",
        "    i_csr_req_valid = 1'b0;",
        *input_initializers,
        "    repeat (4) @(posedge clk);",
        "    rst_n = 1'b1;",
        "    repeat (2) @(posedge clk);",
        *checks,
        f'    $display("{module.name}_tb PASS");',
        "    $finish;",
        "end",
        "",
        f"{module.name} #(",
        "    .CSR_AW (CSR_AW),",
        "    .CSR_DW (CSR_DW)",
        f") u_{module.name}_dut (",
        *formatted,
        ");",
        "",
        "endmodule",
    ])


def _basic_checks(module: ModuleModel) -> list[str]:
    lines: list[str] = []
    writable = next(
        (
            reg for reg in module.registers
            if reg.reg_type in {"cfg", "cmd"} and not reg.special.shadow
        ),
        None,
    )
    if writable:
        field = writable.fields[0]
        mask = ((1 << field.width) - 1) << field.lsb
        lines.extend([
            f"    csr_write(CSR_AW'(32'h{writable.offset:08X}), "
            f"CSR_DW'(64'h{mask:X}));",
            f"    csr_read(CSR_AW'(32'h{writable.offset:08X}), r_read_data);",
            f"    if ((r_read_data & CSR_DW'(64'h{mask:X})) != "
            f"CSR_DW'(64'h{mask:X}))",
            f'        $fatal(1, "{writable.name} write/read mismatch");',
        ])
    readable = next(
        (reg for reg in module.registers if reg.reg_type == "status"),
        None,
    )
    if readable:
        field = readable.fields[0]
        tag = f"{readable.name}_{field.name}"
        suffix = "[0]" if readable.repeat > 1 else ""
        value = min(1, (1 << field.width) - 1)
        lines.extend([
            f"    i_sta_{tag}{suffix} = {field.width}'h{value:X};",
            f"    csr_read(CSR_AW'(32'h{readable.offset:08X}), r_read_data);",
            f"    if (r_read_data[{field.msb}:{field.lsb}] != "
            f"{field.width}'h{value:X})",
            f'        $fatal(1, "{readable.name} status read mismatch");',
        ])
    return lines


def _ral_package(module: ModuleModel) -> str:
    lines = [
        "// Generated UVM register model.",
        f"package {module.name}_ral_pkg;",
        "    import uvm_pkg::*;",
        '    `include "uvm_macros.svh"',
        "",
    ]
    registers = [
        reg for reg in module.registers if reg.reg_type not in {"slave", "mem"}
    ]
    for reg in registers:
        class_name = f"{module.name}_{reg.name}_reg"
        lines.extend([
            f"    class {class_name} extends uvm_reg;",
        ])
        for field in reg.fields:
            lines.append(f"        rand uvm_reg_field {field.name};")
        lines.extend([
            f'        `uvm_object_utils({class_name})',
            "",
            f"        function new(string name = \"{reg.name}\");",
            f"            super.new(name, {module.base_info.reg_bitwidth}, UVM_NO_COVERAGE);",
            "        endfunction",
            "",
            "        virtual function void build();",
        ])
        for field in reg.fields:
            volatile = 1 if reg.reg_type in {"status", "irq"} else 0
            lines.extend([
                f"            {field.name} = uvm_reg_field::type_id::create("
                f"\"{field.name}\");",
                f"            {field.name}.configure(this, {field.width}, "
                f"{field.lsb}, \"{reg.sw_access}\", {volatile}, "
                f"{field.default_for(0)}, 1, 1, 0);",
            ])
        lines.extend([
            "        endfunction",
            "    endclass",
            "",
        ])
    lines.extend([
        f"    class {module.name}_reg_block extends uvm_reg_block;",
        f'        `uvm_object_utils({module.name}_reg_block)',
    ])
    for reg in registers:
        class_name = f"{module.name}_{reg.name}_reg"
        array = f"[{reg.repeat}]" if reg.repeat > 1 else ""
        lines.append(f"        rand {class_name} reg_{reg.name}{array};")
    lines.extend([
        "",
        f"        function new(string name = \"{module.name}_reg_block\");",
        "            super.new(name, UVM_NO_COVERAGE);",
        "        endfunction",
        "",
        "        virtual function void build();",
        f"            default_map = create_map(\"default_map\", 0, "
        f"{module.word_bytes}, UVM_LITTLE_ENDIAN);",
    ])
    for reg in registers:
        class_name = f"{module.name}_{reg.name}_reg"
        if reg.repeat == 1:
            lines.extend([
                f"            reg_{reg.name} = {class_name}::type_id::create("
                f"\"{reg.name}\");",
                f"            reg_{reg.name}.configure(this);",
                f"            reg_{reg.name}.build();",
                f"            default_map.add_reg(reg_{reg.name}, 'h{reg.offset:X}, "
                f"\"{reg.sw_access}\");",
            ])
        else:
            lines.append(
                f"            for (int index = 0; index < {reg.repeat}; index++) begin"
            )
            lines.extend([
                f"                reg_{reg.name}[index] = {class_name}::type_id::create("
                f"$sformatf(\"{reg.name}_%0d\", index));",
                f"                reg_{reg.name}[index].configure(this);",
                f"                reg_{reg.name}[index].build();",
                f"                default_map.add_reg(reg_{reg.name}[index], "
                f"'h{reg.offset:X} + index * {module.word_bytes}, "
                f"\"{reg.sw_access}\");",
                "            end",
            ])
    lines.extend([
        "            lock_model();",
        "        endfunction",
        "    endclass",
        "",
        f"endpackage : {module.name}_ral_pkg",
    ])
    return "\n".join(lines)


def _dims(reg: RegisterModel, field: FieldModel) -> str:
    parts = []
    if reg.repeat > 1:
        parts.append(f"[{reg.repeat - 1}:0]")
    if field.width > 1:
        parts.append(f"[{field.width - 1}:0]")
    return "".join(parts)
