"""Tests for Mamba's file-based import system."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from src.lexer import Lexer
from src.parser import Parser
from src.interpreter import Interpreter


def run_in_dir(main_src, files):
    """Write `files` (dict[name -> source]) into a temp dir, then run main_src
    as if it were main.py inside that dir, capturing stdout."""
    with tempfile.TemporaryDirectory() as d:
        for name, src in files.items():
            with open(os.path.join(d, name), 'w', encoding='utf-8') as f:
                f.write(src)
        main_path = os.path.join(d, "_main.py")
        with open(main_path, 'w', encoding='utf-8') as f:
            f.write(main_src)
        buf = io.StringIO()
        with redirect_stdout(buf):
            interp = Interpreter(file=main_path)
            tree = Parser(Lexer(main_src).tokenize()).parse()
            interp.run(tree)
        return buf.getvalue()


class ImportTests(unittest.TestCase):
    def test_import_module(self):
        out = run_in_dir(
            "import helper\nprint(helper.greet('mamba'))\n",
            {"helper.py": "def greet(name):\n    return 'hi ' + name\n"},
        )
        self.assertEqual(out, "hi mamba\n")

    def test_from_import(self):
        out = run_in_dir(
            "from helper import PI, square\nprint(PI)\nprint(square(4))\n",
            {"helper.py": "PI = 3.14\ndef square(x):\n    return x * x\n"},
        )
        self.assertEqual(out, "3.14\n16\n")

    def test_import_as(self):
        out = run_in_dir(
            "import helper as h\nprint(h.x)\n",
            {"helper.py": "x = 42\n"},
        )
        self.assertEqual(out, "42\n")


if __name__ == "__main__":
    unittest.main()
