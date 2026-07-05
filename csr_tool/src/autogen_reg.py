from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.reg_common import CSRValidationError
    from src.reg_gen_doc import DocGenerator
    from src.reg_gen_firmware import generate_firmware
    from src.reg_gen_rtl import generate_rtl
    from src.reg_gen_tb import generate_tb
    from src.reg_parser import CSRParser
else:
    from .reg_common import CSRValidationError
    from .reg_gen_doc import DocGenerator
    from .reg_gen_firmware import generate_firmware
    from .reg_gen_rtl import generate_rtl
    from .reg_gen_tb import generate_tb
    from .reg_parser import CSRParser


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate CSR RTL, testbench, documentation, and firmware headers."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input register definition (.md, .xlsx, or .json)",
    )
    parser.add_argument(
        "-o",
        "--outdir",
        default="out",
        help="Output directory (default: out)",
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=("single", "nested"),
        default="single",
        help="Generation mode (default: single)",
    )
    parser.add_argument(
        "--nested",
        action="store_true",
        help="Compatibility alias for --mode nested",
    )
    return parser


def run(input_path: str, outdir: str, nested: bool) -> list[Path]:
    source = Path(input_path).resolve()
    output = Path(outdir).resolve()
    module = CSRParser(str(source), nested=nested).parse()
    generated: list[Path] = []
    generated.extend(
        DocGenerator(module, str(output / "doc")).generate_all(is_nested=nested)
    )
    generated.extend(generate_rtl(module, str(output / "rtl")))
    generated.extend(generate_tb(module, str(output / "tb")))
    generated.extend(
        generate_firmware(module, str(output / "firmware"), is_nested=nested)
    )
    return generated


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    nested = args.nested or args.mode == "nested"
    try:
        generated = run(args.input, args.outdir, nested)
    except (CSRValidationError, FileNotFoundError, ImportError, OSError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    print(
        f"[OK] Generated {len(generated)} files in "
        f"{Path(args.outdir).resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
