"""End-to-end feature tests for the Mamba interpreter.

Each case runs a snippet through Mamba and (where possible) compares against
CPython to make sure semantics match.
"""

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


def run_cpython(src):
    return subprocess.run(
        ["python3", "-c", src], capture_output=True, text=True, check=True
    ).stdout


def assert_matches_cpython(testcase, src):
    testcase.assertEqual(run_mamba(src), run_cpython(src))


class ForLoopTests(unittest.TestCase):
    def test_for_range(self):
        src = "for i in range(3):\n    print(i)\n"
        assert_matches_cpython(self, src)

    def test_for_list(self):
        src = "for x in [10, 20, 30]:\n    print(x)\n"
        assert_matches_cpython(self, src)

    def test_for_break_continue(self):
        src = (
            "for i in range(10):\n"
            "    if i == 3:\n"
            "        continue\n"
            "    if i == 6:\n"
            "        break\n"
            "    print(i)\n"
        )
        assert_matches_cpython(self, src)


class ListDictTests(unittest.TestCase):
    def test_list_indexing(self):
        src = "a = [1, 2, 3]\nprint(a[0])\nprint(a[2])\nprint(len(a))\n"
        assert_matches_cpython(self, src)

    def test_list_assign_index(self):
        src = "a = [1, 2, 3]\na[1] = 99\nprint(a[1])\n"
        assert_matches_cpython(self, src)

    def test_dict_lookup(self):
        src = "d = {'a': 1, 'b': 2}\nprint(d['a'])\nprint(d['b'])\n"
        assert_matches_cpython(self, src)

    def test_dict_assign(self):
        src = "d = {}\nd['x'] = 10\nprint(d['x'])\n"
        assert_matches_cpython(self, src)

    def test_tuple(self):
        src = "t = (1, 2, 3)\nprint(t[0])\nprint(len(t))\n"
        assert_matches_cpython(self, src)

    def test_nested(self):
        src = "m = [[1, 2], [3, 4]]\nprint(m[1][0])\n"
        assert_matches_cpython(self, src)


class StringTests(unittest.TestCase):
    def test_concat(self):
        src = "s = 'hello' + ' ' + 'world'\nprint(s)\n"
        assert_matches_cpython(self, src)

    def test_index(self):
        src = "s = 'mamba'\nprint(s[0])\nprint(s[4])\nprint(len(s))\n"
        assert_matches_cpython(self, src)

    def test_method(self):
        # uses Python's str.upper through attribute access on builtin objects
        src = "print('mamba'.upper())\n"
        assert_matches_cpython(self, src)


class TryExceptTests(unittest.TestCase):
    def test_catches_python_exception(self):
        src = (
            "try:\n"
            "    x = 1 / 0\n"
            "except:\n"
            "    print('caught')\n"
        )
        self.assertEqual(run_mamba(src), "caught\n")

    def test_finally_runs(self):
        src = (
            "try:\n"
            "    print('in try')\n"
            "finally:\n"
            "    print('in finally')\n"
        )
        self.assertEqual(run_mamba(src), "in try\nin finally\n")

    def test_raise_and_catch_class(self):
        src = (
            "class Boom:\n"
            "    def __init__(self, msg):\n"
            "        self.message = msg\n"
            "try:\n"
            "    raise Boom('kaboom')\n"
            "except Boom as e:\n"
            "    print(e.message)\n"
        )
        self.assertEqual(run_mamba(src), "kaboom\n")


class ClassTests(unittest.TestCase):
    def test_basic_class(self):
        src = (
            "class Counter:\n"
            "    def __init__(self, start):\n"
            "        self.count = start\n"
            "    def inc(self):\n"
            "        self.count = self.count + 1\n"
            "    def get(self):\n"
            "        return self.count\n"
            "c = Counter(10)\n"
            "c.inc()\n"
            "c.inc()\n"
            "print(c.get())\n"
        )
        self.assertEqual(run_mamba(src), "12\n")

    def test_inheritance(self):
        src = (
            "class A:\n"
            "    def hi(self):\n"
            "        return 'A'\n"
            "class B(A):\n"
            "    pass\n"
            "print(B().hi())\n"
        )
        self.assertEqual(run_mamba(src), "A\n")

    def test_method_override(self):
        src = (
            "class A:\n"
            "    def hi(self):\n"
            "        return 'A'\n"
            "class B(A):\n"
            "    def hi(self):\n"
            "        return 'B'\n"
            "print(B().hi())\n"
        )
        self.assertEqual(run_mamba(src), "B\n")


class OperatorTests(unittest.TestCase):
    def test_floor_div_mod_power(self):
        src = "print(7 // 2)\nprint(7 % 2)\nprint(2 ** 8)\n"
        assert_matches_cpython(self, src)


if __name__ == "__main__":
    unittest.main()
