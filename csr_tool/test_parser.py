import sys
import os
import json

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parser import CSRParser

def test_parser():
    md_path = 'csr_tool/doc/reg_template.md'
    parser = CSRParser(md_path)
    
    try:
        module = parser.parse()
        print("\n[*] Parsing Successful!")
        print(f"Module Name: {module.name}")
        print(f"Base Info: {module.base_info}")
        
        print("\nRegisters:")
        for reg in module.registers:
            print(f"  - {reg.name} @ {hex(reg.offset)} (Type: {reg.reg_type})")
            for field in reg.fields:
                print(f"    * {field.name} [{field.msb}:{field.lsb}] Access: {field.sw_access}")
                
    except Exception as e:
        print(f"\n[!] Parsing Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_parser()
