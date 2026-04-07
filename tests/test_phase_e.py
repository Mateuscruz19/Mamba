"""Phase E tests: Mamba differentiating extensions over CPython.
Block comments, multi-line lambdas, mutable-default-arg fix."""

import unittest

from src.lexer import Lexer
from src.parser import Parser
from src.interpreter import Interpreter
import io
from contextlib import redirect_stdout


def run_mamba(src):
    buf = io.StringIO()
    with redirect_stdout(buf):
        Interpreter().run(Parser(Lexer(src).tokenize()).parse())
    return buf.getvalue()


class BlockCommentTests(unittest.TestCase):
    def test_inline_block_comment(self):
        src = "x = 1 /* inline */ + 2\nprint(x)\n"
        self.assertEqual(run_mamba(src), "3\n")

    def test_multiline_block_comment(self):
        src = (
            "/* this is\n"
            "   a multi-line\n"
            "   comment */\n"
            "print('after')\n"
        )
        self.assertEqual(run_mamba(src), "after\n")

    def test_nested_block_comments(self):
        src = (
            "/* outer /* inner */ still outer */\n"
            "print('ok')\n"
        )
        self.assertEqual(run_mamba(src), "ok\n")


class MultilineLambdaTests(unittest.TestCase):
    def test_basic_multiline(self):
        src = (
            "f = lambda n:\n"
            "    total = 0\n"
            "    for i in range(n):\n"
            "        total += i\n"
            "    return total\n"
            "print(f(5))\n"
        )
        self.assertEqual(run_mamba(src), "10\n")

    def test_classic_inline_still_works(self):
        src = "f = lambda x, y: x * y\nprint(f(3, 4))\n"
        self.assertEqual(run_mamba(src), "12\n")

    def test_multiline_with_branching(self):
        src = (
            "classify = lambda n:\n"
            "    if n > 0:\n"
            "        return 'pos'\n"
            "    if n < 0:\n"
            "        return 'neg'\n"
            "    return 'zero'\n"
            "print(classify(5))\n"
            "print(classify(-1))\n"
            "print(classify(0))\n"
        )
        self.assertEqual(run_mamba(src), "pos\nneg\nzero\n")


class MutableDefaultFixTests(unittest.TestCase):
    """Mamba intentionally diverges from CPython here.
    CPython evaluates default args ONCE at def time, leading to the famous
    `def f(x=[])` footgun. Mamba re-evaluates them on each call."""

    def test_default_list_is_fresh_each_call(self):
        src = (
            "def f(x=[]):\n"
            "    x.append(1)\n"
            "    return x\n"
            "print(f())\n"
            "print(f())\n"
            "print(f())\n"
        )
        # CPython would print [1], [1, 1], [1, 1, 1]
        self.assertEqual(run_mamba(src), "[1]\n[1]\n[1]\n")


if __name__ == "__main__":
    unittest.main()
