from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gen_tb import generate_tb


class GenTbTests(unittest.TestCase):
    def test_generate_empty_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "sim"
            generated = generate_tb(output)
            self.assertIn(output / "README.md", generated)
            self.assertTrue((output / "Makefile").is_file())
            self.assertTrue((output / "ENV.sh").is_file())
            self.assertNotIn("u_", (output / "tb" / "top.sv").read_text())

    def test_generate_with_top_and_filelist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            filelist = root / "project.f"
            filelist.write_text("rtl/soc_top.sv\n", encoding="utf-8")
            output = root / "sim"
            generate_tb(
                output,
                top_module="soc_top",
                filelist=str(filelist),
            )
            self.assertIn(
                "soc_top u_soc_top();",
                (output / "tb" / "top.sv").read_text(encoding="utf-8"),
            )
            self.assertIn(
                f"-f {filelist}",
                (output / "rtl.f").read_text(encoding="utf-8"),
            )

    def test_generate_csh_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "sim"
            generate_tb(output, env_shell="csh")
            self.assertTrue((output / "ENV.csh").is_file())
            self.assertFalse((output / "ENV.sh").exists())
            self.assertIn(
                "source ENV.csh",
                (output / "README.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
