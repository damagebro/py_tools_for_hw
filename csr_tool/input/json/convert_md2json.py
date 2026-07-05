from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.reg_common import write_json
from src.models import ModuleModel
from src.reg_parser import CSRParser


def main() -> int:
    input_dir = ROOT / "input"
    output_dir = input_dir / "json"
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for source in sorted(input_dir.glob("*.md")):
        module = CSRParser(str(source)).parse()
        for reg in module.registers:
            if reg.special.slv_filename:
                child_name = ModuleModel.clean_name(reg.special.slv_filename)
                reg.special.slv_filename = f"{child_name}.json"
        write_json(output_dir / f"{module.name}.json", module.to_dict())
        count += 1
    print(f"[OK] Converted {count} Markdown files to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
