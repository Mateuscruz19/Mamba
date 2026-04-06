"""Tests for comprehensions, lambdas, generators, built-in exceptions,
and with statements."""

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


class ComprehensionTests(unittest.TestCase):
    def test_list_comp(self):
        assert_matches_cpython(self, "print([x*x for x in range(5)])\n")

    def test_list_comp_with_filter(self):
        assert_matches_cpython(
            self, "print([x for x in range(10) if x % 2 == 0])\n"
        )

    def test_nested_for(self):
        assert_matches_cpython(
            self, "print([x*y for x in range(3) for y in range(3)])\n"
        )

    def test_dict_comp(self):
        assert_matches_cpython(self, "print({k: k*k for k in range(4)})\n")

    def test_set_comp(self):
        assert_matches_cpython(self, "print(sorted({x % 3 for x in range(10)}))\n")


class LambdaTests(unittest.TestCase):
    def test_basic(self):
        assert_matches_cpython(self, "add = lambda a, b: a + b\nprint(add(2, 3))\n")

    def test_with_map(self):
        assert_matches_cpython(
            self, "print(list(map(lambda x: x*x, [1,2,3,4])))\n"
        )

    def test_sorted_key(self):
        assert_matches_cpython(
            self,
            "items = [(1, 'b'), (3, 'a'), (2, 'c')]\n"
            "print(sorted(items, key=lambda t: t[1]))\n",
        )

    def test_default(self):
        assert_matches_cpython(
            self, "f = lambda x, y=10: x + y\nprint(f(5))\nprint(f(5, 20))\n"
        )


class GeneratorTests(unittest.TestCase):
    def test_count(self):
        src = (
            "def count(n):\n"
            "    i = 0\n"
            "    while i < n:\n"
            "        yield i\n"
            "        i += 1\n"
            "for x in count(4):\n"
            "    print(x)\n"
        )
        assert_matches_cpython(self, src)

    def test_list_of_gen(self):
        src = (
            "def squares(xs):\n"
            "    for x in xs:\n"
            "        yield x*x\n"
            "print(list(squares([1,2,3,4])))\n"
        )
        assert_matches_cpython(self, src)

    def test_sum_of_gen(self):
        src = (
            "def nums():\n"
            "    for i in range(10):\n"
            "        yield i\n"
            "print(sum(nums()))\n"
        )
        assert_matches_cpython(self, src)


class ExceptionTests(unittest.TestCase):
    def test_value_error(self):
        src = (
            "try:\n"
            "    int('abc')\n"
            "except ValueError:\n"
            "    print('caught')\n"
        )
        self.assertEqual(run_mamba(src), "caught\n")

    def test_tuple_of_exceptions(self):
        src = (
            "try:\n"
            "    raise ValueError('x')\n"
            "except (TypeError, ValueError):\n"
            "    print('ok')\n"
        )
        self.assertEqual(run_mamba(src), "ok\n")

    def test_raise_with_message(self):
        src = (
            "try:\n"
            "    raise RuntimeError('boom')\n"
            "except RuntimeError as e:\n"
            "    print(e)\n"
        )
        self.assertEqual(run_mamba(src), "boom\n")


class WithTests(unittest.TestCase):
    def test_enter_exit(self):
        src = (
            "class Ctx:\n"
            "    def __enter__(self):\n"
            "        print('enter')\n"
            "        return 42\n"
            "    def __exit__(self, et, ev, tb):\n"
            "        print('exit')\n"
            "        return False\n"
            "with Ctx() as v:\n"
            "    print('body', v)\n"
        )
        self.assertEqual(run_mamba(src), "enter\nbody 42\nexit\n")

    def test_exit_runs_on_exception(self):
        src = (
            "class Ctx:\n"
            "    def __enter__(self):\n"
            "        return None\n"
            "    def __exit__(self, et, ev, tb):\n"
            "        print('cleaned')\n"
            "        return True\n"
            "with Ctx():\n"
            "    raise ValueError('x')\n"
            "print('after')\n"
        )
        self.assertEqual(run_mamba(src), "cleaned\nafter\n")


if __name__ == "__main__":
    unittest.main()
