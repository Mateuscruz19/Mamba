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


class OptionalChainingTests(unittest.TestCase):
    def test_attr_on_none_returns_none(self):
        self.assertEqual(run_mamba("x = None\nprint(x?.foo)\n"), "None\n")

    def test_attr_on_object_works(self):
        src = (
            "class A:\n"
            "    def __init__(self):\n"
            "        self.x = 7\n"
            "a = A()\n"
            "print(a?.x)\n"
        )
        self.assertEqual(run_mamba(src), "7\n")

    def test_method_call_on_none(self):
        self.assertEqual(run_mamba("x = None\nprint(x?.foo())\n"), "None\n")

    def test_subscript_on_none(self):
        self.assertEqual(run_mamba("x = None\nprint(x?['k'])\n"), "None\n")

    def test_subscript_missing_key_returns_none(self):
        src = "d = {'a': 1}\nprint(d?['missing'])\n"
        self.assertEqual(run_mamba(src), "None\n")

    def test_chain_short_circuits_after_first_none(self):
        # once any link in the chain is None, the rest auto-shortcircuits
        src = "x = None\nprint(x?.a.b.c)\n"
        self.assertEqual(run_mamba(src), "None\n")

    def test_chain_with_missing_attr(self):
        src = (
            "class A:\n"
            "    pass\n"
            "a = A()\n"
            "print(a?.missing?.deeper)\n"
        )
        self.assertEqual(run_mamba(src), "None\n")

    def test_combined_with_coalesce(self):
        src = "x = None\nprint(x?.foo ?? 'default')\n"
        self.assertEqual(run_mamba(src), "default\n")


class MatchExprTests(unittest.TestCase):
    def test_basic_int_match(self):
        src = (
            "def f(x):\n"
            "    return match x { 1 => 'a', 2 => 'b', _ => 'z' }\n"
            "print(f(1))\n"
            "print(f(2))\n"
            "print(f(99))\n"
        )
        self.assertEqual(run_mamba(src), "a\nb\nz\n")

    def test_string_match(self):
        src = (
            "print(match 'pt' { 'en' => 1, 'pt' => 2, _ => 0 })\n"
        )
        self.assertEqual(run_mamba(src), "2\n")

    def test_match_in_expression_position(self):
        src = "print((match 3 { 3 => 30, _ => 0 }) + 5)\n"
        self.assertEqual(run_mamba(src), "35\n")

    def test_no_match_raises(self):
        src = "print(match 5 { 1 => 'a', 2 => 'b' })\n"
        with self.assertRaises(ValueError):
            run_mamba(src)

    def test_match_none(self):
        src = "print(match None { None => 'nil', _ => 'other' })\n"
        self.assertEqual(run_mamba(src), "nil\n")

    def test_match_evaluates_pattern_expr(self):
        # patterns are full expressions, can reference variables
        src = (
            "k = 10\n"
            "print(match 10 { k => 'eq', _ => 'no' })\n"
        )
        self.assertEqual(run_mamba(src), "eq\n")


if __name__ == "__main__":
    unittest.main()
