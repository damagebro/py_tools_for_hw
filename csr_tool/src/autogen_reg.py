import argparse
import os
import sys

# Add the project root to sys.path to allow imports from .models, etc.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from src.reg_parser import CSRParser
    from src.reg_gen_doc import DocGenerator
    from src.reg_gen_rtl import generate_rtl
    from src.reg_gen_tb import generate_tb
    from src.reg_gen_firmware import generate_firmware
except ImportError:
    from reg_parser import CSRParser
    from reg_gen_doc import DocGenerator
    from reg_gen_rtl import generate_rtl
    from reg_gen_tb import generate_tb
    from reg_gen_firmware import generate_firmware

def main():
    parser = argparse.ArgumentParser(description="CSR Autogen Tool")
    parser.add_argument("-i", "--input", required=True, help="Input register definition file (.md)")
    parser.add_argument("--nested", action="store_true", help="Generate nested tree structures")
    parser.add_argument("-o", "--outdir", default="csr_tool/out", help="Output directory")

    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        print(f"[!] Input file not found: {input_path}")
        sys.exit(1)

    print(f"[*] Input: {input_path}")
    if args.nested:
        print(f"[*] Mode: nested")
    else:
        print(f"[*] Mode: single")

    # 1. Parsing
    parser_obj = CSRParser(input_path, nested=args.nested)
    try:
        module = parser_obj.parse()
        print(f"[*] Parsing successful: {module.name}")
    except Exception as e:
        print(f"[!] Parsing failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 2. Documentation Generation
    doc_out_dir = os.path.join(args.outdir, "doc")
    doc_gen = DocGenerator(module, doc_out_dir)
    doc_gen.generate_all(is_nested=args.nested)

    # 3. RTL Generation
    rtl_out_dir = os.path.join(args.outdir, "rtl")
    generate_rtl(module, rtl_out_dir)

    # 4. Testbench Generation
    tb_out_dir = os.path.join(args.outdir, "tb")
    generate_tb(module, tb_out_dir)

    # 5. Firmware Generation
    fw_out_dir = os.path.join(args.outdir, "firmware")
    generate_firmware(module, fw_out_dir, is_nested=args.nested)

    print(f"\n[*] All tasks completed. Outputs in {args.outdir}/")

if __name__ == "__main__":
    main()
