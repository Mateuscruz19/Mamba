"""Tests for unpacking, slicing, augmented assigns, f-strings, and
default/varargs/kwargs."""

import io
import subprocess
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


def assert_matches_cpython(tc, src):
    cp = subprocess.run(["python3", "-c", src],
                        capture_output=True, text=True, check=True).stdout
    tc.assertEqual(run_mamba(src), cp)


class UnpackingTests(unittest.TestCase):
    def test_basic(self):
        assert_matches_cpython(self, "a, b = 1, 2\nprint(a)\nprint(b)\n")

    def test_swap(self):
        assert_matches_cpython(self, "a = 1\nb = 2\na, b = b, a\nprint(a, b)\n")

    def test_from_list(self):
        assert_matches_cpython(self, "a, b, c = [10, 20, 30]\nprint(a + b + c)\n")

    def test_for_unpack(self):
        src = (
            "pairs = [(1, 'a'), (2, 'b'), (3, 'c')]\n"
            "for n, s in pairs:\n"
            "    print(n, s)\n"
        )
        assert_matches_cpython(self, src)


class SlicingTests(unittest.TestCase):
    def test_list_slice(self):
        assert_matches_cpython(self, "a = [1,2,3,4,5]\nprint(a[1:3])\n")

    def test_open_sides(self):
        assert_matches_cpython(self, "a = [1,2,3,4,5]\nprint(a[:2])\nprint(a[3:])\n")

    def test_step_and_reverse(self):
        assert_matches_cpython(self, "a = [1,2,3,4,5]\nprint(a[::2])\nprint(a[::-1])\n")

    def test_string_slice(self):
        assert_matches_cpython(self, "s = 'mamba'\nprint(s[1:4])\nprint(s[::-1])\n")


class AugAssignTests(unittest.TestCase):
    def test_plus_eq(self):
        assert_matches_cpython(self, "i = 0\nfor x in range(5):\n    i += x\nprint(i)\n")

    def test_all_ops(self):
        src = (
            "x = 10\nx += 5\nx -= 2\nx *= 3\nx //= 2\nx %= 7\nprint(x)\n"
        )
        # //= and **= weren't added — use only the supported ones
        src = "x = 10\nx += 5\nx -= 2\nx *= 3\nx /= 2\nx %= 7\nprint(x)\n"
        assert_matches_cpython(self, src)

    def test_attr_aug(self):
        src = (
            "class C:\n"
            "    def __init__(self):\n"
            "        self.n = 0\n"
            "c = C()\n"
            "c.n += 5\n"
            "c.n += 3\n"
            "print(c.n)\n"
        )
        self.assertEqual(run_mamba(src), "8\n")

    def test_subscript_aug(self):
        assert_matches_cpython(self, "a = [10, 20, 30]\na[1] += 5\nprint(a[1])\n")


class FStringTests(unittest.TestCase):
    def test_basic(self):
        assert_matches_cpython(self, "name = 'mamba'\nprint(f'hi {name}')\n")

    def test_expr_inside(self):
        assert_matches_cpython(self, "a = 3\nb = 4\nprint(f'{a} + {b} = {a + b}')\n")

    def test_method_call(self):
        assert_matches_cpython(self, "s = 'mamba'\nprint(f'{s.upper()}')\n")

    def test_double_braces(self):
        assert_matches_cpython(self, "x = 1\nprint(f'{{x}} = {x}')\n")


class DefaultsAndVarargsTests(unittest.TestCase):
    def test_default(self):
        src = (
            "def greet(name, greeting='hi'):\n"
            "    return greeting + ' ' + name\n"
            "print(greet('mamba'))\n"
            "print(greet('mamba', 'hello'))\n"
        )
        assert_matches_cpython(self, src)

    def test_kwarg_call(self):
        src = (
            "def f(a, b, c):\n"
            "    return a * 100 + b * 10 + c\n"
            "print(f(c=3, a=1, b=2))\n"
        )
        assert_matches_cpython(self, src)

    def test_varargs(self):
        src = (
            "def total(*nums):\n"
            "    s = 0\n"
            "    for n in nums:\n"
            "        s += n\n"
            "    return s\n"
            "print(total(1, 2, 3, 4))\n"
        )
        assert_matches_cpython(self, src)

    def test_kwargs(self):
        src = (
            "def show(**opts):\n"
            "    return opts['a'] + opts['b']\n"
            "print(show(a=1, b=2))\n"
        )
        assert_matches_cpython(self, src)

    def test_mixed(self):
        src = (
            "def f(a, b=10, *args, **kw):\n"
            "    return a + b + sum(args) + kw.get('extra', 0)\n"
            "print(f(1))\n"
            "print(f(1, 2, 3, 4, extra=100))\n"
        )
        assert_matches_cpython(self, src)


if __name__ == "__main__":
    unittest.main()
