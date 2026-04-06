import io
import unittest
from contextlib import redirect_stdout

from src.lexer import Lexer
from src.parser import Parser
from src.interpreter import Interpreter


def run_capture(src):
    buf = io.StringIO()
    with redirect_stdout(buf):
        Interpreter().run(Parser(Lexer(src).tokenize()).parse())
    return buf.getvalue()


class InterpreterTests(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(run_capture("print(1 + 2 * 3)\n"), "7\n")

    def test_variables(self):
        self.assertEqual(run_capture("x = 10\nprint(x + 5)\n"), "15\n")

    def test_if_else(self):
        src = "x = 5\nif x > 3:\n    print('big')\nelse:\n    print('small')\n"
        self.assertEqual(run_capture(src), "big\n")

    def test_while_counter(self):
        src = "i = 0\nwhile i < 3:\n    print(i)\n    i = i + 1\n"
        self.assertEqual(run_capture(src), "0\n1\n2\n")

    def test_recursive_function(self):
        src = (
            "def fact(n):\n"
            "    if n <= 1:\n"
            "        return 1\n"
            "    return n * fact(n - 1)\n"
            "print(fact(5))\n"
        )
        self.assertEqual(run_capture(src), "120\n")

    def test_closure(self):
        src = (
            "def make_adder(x):\n"
            "    def add(y):\n"
            "        return x + y\n"
            "    return add\n"
            "add5 = make_adder(5)\n"
            "print(add5(10))\n"
        )
        self.assertEqual(run_capture(src), "15\n")

    def test_bool_short_circuit(self):
        # If 'or' didn't short-circuit, the second call would error
        src = (
            "def boom():\n"
            "    return 1 / 0\n"
            "print(True or boom())\n"
        )
        self.assertEqual(run_capture(src), "True\n")


class CPythonOracleTests(unittest.TestCase):
    """Run a snippet through Mamba and compare with CPython's output."""

    CASES = [
        "print(1 + 2)\n",
        "x = 10\ny = 20\nprint(x * y)\n",
        "def f(n):\n    if n <= 1:\n        return 1\n    return n * f(n - 1)\nprint(f(6))\n",
        "i = 0\nwhile i < 5:\n    print(i)\n    i = i + 1\n",
    ]

    def test_matches_cpython(self):
        import subprocess
        for src in self.CASES:
            with self.subTest(src=src):
                mamba = run_capture(src)
                cp = subprocess.run(
                    ["python3", "-c", src],
                    capture_output=True, text=True, check=True,
                ).stdout
                self.assertEqual(mamba, cp)


if __name__ == "__main__":
    unittest.main()
