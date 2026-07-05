import os
import sys

# Add src to path to import modules
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'src')
sys.path.append(src_dir)

from reg_parser import CSRParser
from reg_gen_doc import DocGenerator

def convert_md_to_xlsx():
    out_dir = os.path.dirname(__file__)
    input_dir = os.path.dirname(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    for f in os.listdir(input_dir):
        if f.endswith('.md'):
            md_path = os.path.join(input_dir, f)
            parser = CSRParser(md_path, nested=False)
            module = parser.parse(md_path)
            
            gen = DocGenerator(module, out_dir)
            gen.generate_excel(is_nested=False)
            
            old_path = os.path.join(out_dir, f"{module.name}_gen.xlsx")
            new_path = os.path.join(out_dir, f"{module.name}.xlsx")
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
    
    print("Conversion complete: .md -> .xlsx in input/xlsx/")

if __name__ == "__main__":
    convert_md_to_xlsx()
