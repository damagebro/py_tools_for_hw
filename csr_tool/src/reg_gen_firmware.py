import os

def get_block_name(module_name):
    if module_name.endswith('_reg'):
        return module_name[:-4]
    elif module_name.endswith('_register'):
        return module_name[:-9]
    return module_name

class NodeInstance:
    def __init__(self, module):
        self.module = module
        self.base_addr = module.base_address
        self.block_name = get_block_name(module.name)
        self.unique_block_name = self.block_name

def collect_instances(module, instances):
    inst = NodeInstance(module)
    instances.append(inst)
    for sub in module.sub_modules:
        collect_instances(sub.module_obj, instances)

def get_reg_default(reg):
    if not reg.fields:
        return 0
    val = 0
    for field in reg.fields:
        if field.default_value:
            try:
                if isinstance(field.default_value, str) and field.default_value.lower().startswith('0x'):
                    f_val = int(field.default_value, 16)
                else:
                    f_val = int(field.default_value)
                val |= (f_val << field.lsb)
            except ValueError:
                pass
    return val

def generate_firmware(module, out_dir, is_nested=False):
    if not is_nested:
        print(f"[*] Firmware generation is only supported in nested mode. Skipping.")
        return

    os.makedirs(out_dir, exist_ok=True)
    
    sys_prefix = module.base_info.system_prefix
    sys_prefix_macro = f"{sys_prefix.upper()}_" if sys_prefix else ""
    
    instances = []
    collect_instances(module, instances)
    
    # Uniquify block names
    block_name_counts = {}
    for inst in instances:
        block_name_counts[inst.block_name] = block_name_counts.get(inst.block_name, 0) + 1
        
    block_name_seen = {}
    for inst in instances:
        if block_name_counts[inst.block_name] > 1:
            block_name_seen[inst.block_name] = block_name_seen.get(inst.block_name, 0) + 1
            inst.unique_block_name = f"{inst.block_name}_u{block_name_seen[inst.block_name]}"
            
    # Collect unique block types
    block_types = {}
    for inst in instances:
        if inst.block_name not in block_types:
            block_types[inst.block_name] = inst.module

    top_block_name = get_block_name(module.name)
    addr_h_path = os.path.join(out_dir, f"{top_block_name}_all_reg_addr.h")
    type_h_path = os.path.join(out_dir, f"{top_block_name}_all_reg_type.h")
    
    # ---------------------------------------------------------
    # Generate xxx_all_reg_addr.h
    # ---------------------------------------------------------
    addr_lines = []
    addr_lines.append(f"#ifndef __{top_block_name.upper()}_ALL_REG_ADDR_H__")
    addr_lines.append(f"#define __{top_block_name.upper()}_ALL_REG_ADDR_H__\n")
    
    # a. Address map comment
    addr_lines.append("/*")
    addr_lines.append(" * Address Map:")
    for inst in instances:
        depth = inst.module.excel_path.count(os.sep) # rough depth, better to pass depth in collect_instances
        # Let's just print a flat list for simplicity, or we can format it nicely
        addr_lines.append(f" * {inst.unique_block_name:<20} : 0x{inst.base_addr:08X}")
    addr_lines.append(" */\n")
    
    # b. Block offsets and defaults
    addr_lines.append("// --- Block Register Offsets & Defaults ---")
    
    max_offset_len = 0
    max_default_len = 0
    for b_name, b_mod in block_types.items():
        for reg in b_mod.registers:
            offset_macro = f"{b_name.upper()}_{reg.name.upper()}_OFFSET"
            max_offset_len = max(max_offset_len, len(offset_macro))
            if reg.reg_type not in ['slave', 'mem']:
                default_macro = f"{b_name.upper()}_{reg.name.upper()}_DEFAULT"
                max_default_len = max(max_default_len, len(default_macro))
                
    for b_name, b_mod in block_types.items():
        addr_lines.append(f"\n// Block: {b_name}")
        for reg in b_mod.registers:
            rel_offset = reg.offset - b_mod.base_address
            offset_macro = f"{b_name.upper()}_{reg.name.upper()}_OFFSET"
            addr_lines.append(f"#define {offset_macro:<{max_offset_len}} 0x{rel_offset:04X}")
            if reg.reg_type not in ['slave', 'mem']:
                default_val = get_reg_default(reg)
                default_macro = f"{b_name.upper()}_{reg.name.upper()}_DEFAULT"
                addr_lines.append(f"#define {default_macro:<{max_default_len}} 0x{default_val:08X}")
                
    # c. Absolute addresses
    addr_lines.append("\n// --- Absolute Addresses ---")
    
    max_addr_len = 0
    for inst in instances:
        base_macro = f"{sys_prefix_macro}{inst.unique_block_name.upper()}_BASE_ADDR"
        max_addr_len = max(max_addr_len, len(base_macro))
        for reg in inst.module.registers:
            addr_macro = f"{sys_prefix_macro}{inst.unique_block_name.upper()}_{reg.name.upper()}_ADDR"
            max_addr_len = max(max_addr_len, len(addr_macro))
            
    for inst in instances:
        addr_lines.append(f"\n// Instance: {inst.unique_block_name}")
        base_macro = f"{sys_prefix_macro}{inst.unique_block_name.upper()}_BASE_ADDR"
        addr_lines.append(f"#define {base_macro:<{max_addr_len}} 0x{inst.base_addr:08X}")
        for reg in inst.module.registers:
            addr_macro = f"{sys_prefix_macro}{inst.unique_block_name.upper()}_{reg.name.upper()}_ADDR"
            offset_macro = f"{inst.block_name.upper()}_{reg.name.upper()}_OFFSET"
            addr_lines.append(f"#define {addr_macro:<{max_addr_len}} ({sys_prefix_macro}{inst.unique_block_name.upper()}_BASE_ADDR + {offset_macro})")
            
    addr_lines.append(f"\n#endif // __{top_block_name.upper()}_ALL_REG_ADDR_H__")
    
    with open(addr_h_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(addr_lines))
    print(f"[*] Generating Firmware Header: {addr_h_path}")
    
    # ---------------------------------------------------------
    # Generate xxx_all_reg_type.h
    # ---------------------------------------------------------
    type_lines = []
    type_lines.append(f"#ifndef __{top_block_name.upper()}_ALL_REG_TYPE_H__")
    type_lines.append(f"#define __{top_block_name.upper()}_ALL_REG_TYPE_H__\n")
    type_lines.append("#include <stdint.h>")
    type_lines.append("typedef uint32_t u32;\n")
    type_lines.append(f'#include "{top_block_name}_all_reg_addr.h"\n')
    
    # 1. Unions for each block
    for b_name, b_mod in block_types.items():
        type_lines.append(f"// =====================================================")
        type_lines.append(f"// Block: {b_name}")
        type_lines.append(f"// =====================================================")
        
        for reg in b_mod.registers:
            if reg.reg_type in ['slave', 'mem']:
                continue
                
            type_lines.append(f"typedef union {{")
            
            # Determine SW_access for the whole register (usually the same for all fields, or we can just use the first field's access)
            sw_access = reg.fields[0].sw_access if reg.fields else "RW"
            type_lines.append(f"    struct {{ // SW_access={sw_access}, reg_type={reg.reg_type}")
            
            if not reg.fields:
                type_lines.append("        u32 value : 32;")
            else:
                current_bit = 0
                sorted_fields = sorted(reg.fields, key=lambda f: f.lsb)
                for f in sorted_fields:
                    if f.lsb > current_bit:
                        gap = f.lsb - current_bit
                        if gap == 1:
                            type_lines.append(f"        u32 rsv{current_bit} : 1;")
                        else:
                            type_lines.append(f"        u32 rsv{f.lsb - 1}_{current_bit} : {gap};")
                    
                    width = f.msb - f.lsb + 1
                    def_val_str = f.default_value if f.default_value else "0x0"
                    type_lines.append(f"        u32 {f.name} : {width}; // default = {def_val_str}")
                    current_bit = f.msb + 1
                    
                if current_bit < 32:
                    gap = 32 - current_bit
                    if gap == 1:
                        type_lines.append(f"        u32 rsv{current_bit} : 1;")
                    else:
                        type_lines.append(f"        u32 rsv31_{current_bit} : {gap};")
                        
            type_lines.append("    } bits;")
            type_lines.append("    u32 word;")
            type_lines.append(f"}} {b_name}_{reg.name}_tu;\n")
            
        # Struct for the block
        type_lines.append(f"typedef struct {{")
        for reg in b_mod.registers:
            if reg.reg_type in ['slave', 'mem']:
                continue
                
            repeat_count = 1
            for part in reg.special.split(','):
                part = part.strip()
                if part.startswith('repeat'):
                    try:
                        repeat_count = int(part.split()[1])
                    except ValueError:
                        pass
                        
            if repeat_count > 1:
                type_lines.append(f"    {b_name}_{reg.name}_tu {reg.name}[{repeat_count}];")
            else:
                type_lines.append(f"    {b_name}_{reg.name}_tu {reg.name};")
                    
        type_lines.append(f"}} {b_name}_reg_ts;\n")
        
    # 2. Mapping of reg_addr -> reg_default_value
    type_lines.append("// =====================================================")
    type_lines.append("// Address to Default Value Mapping")
    type_lines.append("// =====================================================")
    type_lines.append("typedef struct {")
    type_lines.append("    const uint32_t addr;     /* 寄存器绝对地址或偏移 */")
    type_lines.append("    const uint32_t rst_val;  /* 寄存器复位默认值 */")
    type_lines.append("} reg_init_t;\n")
    
    type_lines.append("/* * * 自动生成的硬件初始化映射表")
    type_lines.append(" * 每个 Block 独立生成一份初始化映射表")
    type_lines.append(" */\n")
    
    for inst in instances:
        struct_name = f"{sys_prefix_macro.lower()}{inst.unique_block_name.lower()}_init_ts"
        var_name = f"{sys_prefix_macro.lower()}{inst.unique_block_name.lower()}_init"
        
        type_lines.append(f"typedef const struct {{")
        for reg in inst.module.registers:
            if reg.reg_type in ['slave', 'mem']:
                continue
            repeat_count = 1
            for part in reg.special.split(','):
                part = part.strip()
                if part.startswith('repeat'):
                    try: repeat_count = int(part.split()[1])
                    except: pass
            if repeat_count > 1:
                type_lines.append(f"    reg_init_t {reg.name}[{repeat_count}];")
            else:
                type_lines.append(f"    reg_init_t {reg.name};")
        type_lines.append(f"}} {struct_name};\n")
        
        type_lines.append(f"static {struct_name} {var_name} = {{")
        for reg in inst.module.registers:
            if reg.reg_type in ['slave', 'mem']:
                continue
            addr_macro = f"{sys_prefix_macro}{inst.unique_block_name.upper()}_{reg.name.upper()}_ADDR"
            def_macro = f"{inst.block_name.upper()}_{reg.name.upper()}_DEFAULT"
            
            repeat_count = 1
            for part in reg.special.split(','):
                part = part.strip()
                if part.startswith('repeat'):
                    try: repeat_count = int(part.split()[1])
                    except: pass
            
            if repeat_count > 1:
                type_lines.append(f"    .{reg.name} = {{")
                for i in range(repeat_count):
                    offset_str = f" + 0x{i*4:X}" if i > 0 else ""
                    type_lines.append(f"        {{ .addr = {addr_macro}{offset_str}, .rst_val = {def_macro} }},")
                type_lines.append(f"    }},")
            else:
                type_lines.append(f"    .{reg.name} = {{ .addr = {addr_macro}, .rst_val = {def_macro} }},")
        type_lines.append("};\n")
    
    type_lines.append(f"#endif // __{top_block_name.upper()}_ALL_REG_TYPE_H__")
    
    with open(type_h_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(type_lines))
    print(f"[*] Generating Firmware Header: {type_h_path}")
