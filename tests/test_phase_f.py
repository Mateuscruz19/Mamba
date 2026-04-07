"""Phase F tests: Mamba differentiating syntax extensions —
pipe operator, none-aware operators, etc."""

import io
import unittest
from contextlib import redirect_stdout

from src.lexer import Lexer
from src.parser import Parser
from src.interpreter import Interpreter


def run_mamba(src):
    buf = io.StringIO()
    with redirect_stdout(buf):
        Interpreter().run(Parser(Lexer(src).tokenize()).parse())
    return buf.getvalue()


class PipeOperatorTests(unittest.TestCase):
    def test_simple_pipe(self):
        src = (
            "def double(x):\n"
            "    return x * 2\n"
            "print(5 |> double)\n"
        )
        self.assertEqual(run_mamba(src), "10\n")

    def test_chained_pipes(self):
        src = "print([1,2,3,4,5] |> map(lambda x: x*x) |> list)\n"
        self.assertEqual(run_mamba(src), "[1, 4, 9, 16, 25]\n")

    def test_pipe_appends_by_default(self):
        # filter(pred, iter): default append puts iter last, matching stdlib
        src = "print([1,-2,3,-4,5] |> filter(lambda x: x > 0) |> list)\n"
        self.assertEqual(run_mamba(src), "[1, 3, 5]\n")

    def test_pipe_placeholder_underscore(self):
        src = (
            "def sub(a, b):\n"
            "    return a - b\n"
            "print(10 |> sub(_, 3))\n"
            "print(10 |> sub(3, _))\n"
        )
        self.assertEqual(run_mamba(src), "7\n-7\n")

    def test_pipe_method_reference(self):
        src = "print('  hi  ' |> str.strip |> str.upper)\n"
        self.assertEqual(run_mamba(src), "HI\n")

    def test_pipe_left_associative(self):
        # ((1 |> double) |> double) == 4
        src = (
            "def double(x):\n"
            "    return x * 2\n"
            "print(1 |> double |> double)\n"
        )
        self.assertEqual(run_mamba(src), "4\n")


class NoneCoalesceTests(unittest.TestCase):
    def test_left_not_none(self):
        self.assertEqual(run_mamba("print(5 ?? 99)\n"), "5\n")

    def test_left_none(self):
        self.assertEqual(run_mamba("print(None ?? 99)\n"), "99\n")

    def test_chained(self):
        self.assertEqual(run_mamba("print(None ?? None ?? 'ok')\n"), "ok\n")

    def test_short_circuits_right(self):
        # right side must NOT be evaluated when left is not None
        src = (
            "def boom():\n"
            "    raise ValueError('should not run')\n"
            "print(7 ?? boom())\n"
        )
        self.assertEqual(run_mamba(src), "7\n")

    def test_falsy_but_not_none_returns_left(self):
        # 0, '', [] are falsy but NOT None — ?? must return them
        self.assertEqual(run_mamba("print(0 ?? 99)\n"), "0\n")
        self.assertEqual(run_mamba("print('' ?? 'x')\n"), "\n")


if __name__ == "__main__":
    unittest.main()
