"""Phase C tests: builtins, ternary, chained comparisons, assert/del,
star/double-star unpacking."""

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


class BuiltinTests(unittest.TestCase):
    def test_all_any(self):
        assert_matches_cpython(self, "print(all([1,2,3]))\nprint(any([0,0,1]))\n")

    def test_round_divmod_pow(self):
        assert_matches_cpython(self, "print(round(3.7))\nprint(divmod(10,3))\nprint(pow(2,8))\n")

    def test_chr_ord(self):
        assert_matches_cpython(self, "print(chr(65), ord('A'))\n")

    def test_hex_bin_oct(self):
        assert_matches_cpython(self, "print(hex(255), bin(5), oct(8))\n")

    def test_set_constructor(self):
        assert_matches_cpython(self, "print(sorted(set([1,2,2,3])))\n")

    def test_callable(self):
        src = "print(callable(print))\nprint(callable(42))\n"
        assert_matches_cpython(self, src)

    def test_getattr_hasattr_default(self):
        src = (
            "class C:\n"
            "    x = 1\n"
            "print(getattr(C, 'x'))\n"
            "print(getattr(C, 'y', 99))\n"
            "print(hasattr(C, 'x'), hasattr(C, 'y'))\n"
        )
        self.assertEqual(run_mamba(src), "1\n99\nTrue False\n")


class TernaryTests(unittest.TestCase):
    def test_basic(self):
        assert_matches_cpython(self, "print('yes' if 1 else 'no')\n")

    def test_in_comprehension(self):
        assert_matches_cpython(
            self,
            "print([x*2 if x > 0 else 0 for x in [-1,1,-2,2]])\n",
        )


class ChainedComparisonTests(unittest.TestCase):
    def test_three_way(self):
        assert_matches_cpython(self, "print(1 < 2 < 3)\nprint(1 < 2 < 0)\n")

    def test_inclusive(self):
        assert_matches_cpython(self, "print(0 <= 5 <= 10)\n")

    def test_equality_chain(self):
        assert_matches_cpython(self, "print(1 == 1 == 1)\n")


class AssertDelTests(unittest.TestCase):
    def test_assert_passes(self):
        run_mamba("assert 1 == 1\n")

    def test_assert_fails_with_msg(self):
        src = (
            "try:\n"
            "    assert False, 'oops'\n"
            "except AssertionError as e:\n"
            "    print(e)\n"
        )
        self.assertEqual(run_mamba(src), "oops\n")

    def test_del_name(self):
        src = (
            "x = 5\n"
            "del x\n"
            "try:\n"
            "    print(x)\n"
            "except NameError:\n"
            "    print('gone')\n"
        )
        self.assertEqual(run_mamba(src), "gone\n")

    def test_del_dict_key(self):
        src = "d = {'a':1,'b':2}\ndel d['a']\nprint(d)\n"
        assert_matches_cpython(self, src)


class StarUnpackingTests(unittest.TestCase):
    def test_star_call(self):
        src = (
            "def f(a,b,c):\n"
            "    return a+b+c\n"
            "args=[1,2,3]\n"
            "print(f(*args))\n"
        )
        assert_matches_cpython(self, src)

    def test_kwargs_call(self):
        src = (
            "def f(a,b):\n"
            "    return a-b\n"
            "d={'a':10,'b':3}\n"
            "print(f(**d))\n"
        )
        assert_matches_cpython(self, src)

    def test_star_in_list(self):
        assert_matches_cpython(self, "a=[1,2]\nb=[3,4]\nprint([*a,*b,5])\n")

    def test_star_in_dict(self):
        assert_matches_cpython(
            self,
            "a={'x':1}\nb={'y':2}\nprint({**a,**b,'z':3})\n",
        )

    def test_star_in_set(self):
        assert_matches_cpython(self, "print(sorted({*[1,2],*[3,4]}))\n")


if __name__ == "__main__":
    unittest.main()
