"""Phase G tests: real runtime function overloading.

Unlike CPython's typing.overload (which is purely a static-checker hint),
Mamba's @overload actually dispatches at call time based on arity and,
optionally, runtime types."""

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


class ArityOverloadTests(unittest.TestCase):
    def test_dispatch_by_arity(self):
        src = (
            "@overload\n"
            "def area(r):\n"
            "    return 3 * r * r\n"
            "@overload\n"
            "def area(w, h):\n"
            "    return w * h\n"
            "print(area(5))\n"
            "print(area(3, 4))\n"
        )
        self.assertEqual(run_mamba(src), "75\n12\n")

    def test_no_arity_match_raises(self):
        src = (
            "@overload\n"
            "def f(x):\n"
            "    return x\n"
            "@overload\n"
            "def f(x, y):\n"
            "    return x + y\n"
            "f(1, 2, 3)\n"
        )
        with self.assertRaises(TypeError):
            run_mamba(src)


class TypeOverloadTests(unittest.TestCase):
    def test_dispatch_by_builtin_type(self):
        src = (
            "@overload(int)\n"
            "def kind(x):\n        return 'int'\n"
            "@overload(str)\n"
            "def kind(x):\n        return 'str'\n"
            "@overload(list)\n"
            "def kind(x):\n        return 'list'\n"
            "print(kind(42))\n"
            "print(kind('hi'))\n"
            "print(kind([1,2]))\n"
        )
        self.assertEqual(run_mamba(src), "int\nstr\nlist\n")

    def test_dispatch_by_user_class_with_mro(self):
        src = (
            "class Animal:\n"
            "    pass\n"
            "class Dog(Animal):\n"
            "    pass\n"
            "@overload(Dog)\n"
            "def speak(a):\n        return 'woof'\n"
            "@overload(Animal)\n"
            "def speak(a):\n        return 'noise'\n"
            "print(speak(Dog()))\n"
            "print(speak(Animal()))\n"
        )
        self.assertEqual(run_mamba(src), "woof\nnoise\n")

    def test_type_branches_take_priority_over_arity(self):
        # untyped arity branch should be a fallback after typed branches
        src = (
            "@overload\n"
            "def f(x):\n        return 'fallback'\n"
            "@overload(int)\n"
            "def f(x):\n        return 'int'\n"
            "print(f(5))\n"
            "print(f('hi'))\n"
        )
        self.assertEqual(run_mamba(src), "int\nfallback\n")

    def test_no_type_match_raises(self):
        src = (
            "@overload(int)\n"
            "def f(x):\n        return x\n"
            "f('hi')\n"
        )
        with self.assertRaises(TypeError):
            run_mamba(src)


class OverloadIntegrationTests(unittest.TestCase):
    def test_overload_inside_recursion(self):
        src = (
            "@overload(int)\n"
            "def collapse(x):\n        return x\n"
            "@overload(list)\n"
            "def collapse(xs):\n"
            "    total = 0\n"
            "    for v in xs:\n"
            "        total += collapse(v)\n"
            "    return total\n"
            "print(collapse([1, 2, 3, 4]))\n"
        )
        self.assertEqual(run_mamba(src), "10\n")

    def test_overload_combined_with_match(self):
        src = (
            "@overload(int)\n"
            "def label(x):\n        return match x { 0 => 'zero', _ => 'nonzero' }\n"
            "@overload(str)\n"
            "def label(x):\n        return 'text:' + x\n"
            "print(label(0))\n"
            "print(label(7))\n"
            "print(label('hi'))\n"
        )
        self.assertEqual(run_mamba(src), "zero\nnonzero\ntext:hi\n")


if __name__ == "__main__":
    unittest.main()
