"""Phase H tests: load-bearing typing.

Annotations are parsed and stored on the AST. By default they are *not*
enforced — the interpreter ignores them, matching Python's runtime behavior.
The @typed decorator opts a function in to runtime checking against its own
annotations, including return types and user classes (with MRO)."""

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


class AnnotationParsingTests(unittest.TestCase):
    def test_param_and_return_annotations_dont_enforce_by_default(self):
        # mismatched call must still succeed without @typed
        src = (
            "def add(x: int, y: int) -> int:\n"
            "    return x + y\n"
            "print(add('a', 'b'))\n"
        )
        self.assertEqual(run_mamba(src), "ab\n")

    def test_variable_annotation_with_value(self):
        src = "n: int = 42\nprint(n)\n"
        self.assertEqual(run_mamba(src), "42\n")

    def test_bare_variable_annotation_is_noop(self):
        src = "x: int\nx = 5\nprint(x)\n"
        self.assertEqual(run_mamba(src), "5\n")

    def test_default_after_annotation(self):
        src = (
            "def greet(name: str = 'world') -> str:\n"
            "    return 'hi ' + name\n"
            "print(greet())\n"
            "print(greet('ada'))\n"
        )
        self.assertEqual(run_mamba(src), "hi world\nhi ada\n")


class TypedDecoratorTests(unittest.TestCase):
    def test_typed_passes_correct_args(self):
        src = (
            "@typed\n"
            "def add(x: int, y: int) -> int:\n"
            "    return x + y\n"
            "print(add(2, 3))\n"
        )
        self.assertEqual(run_mamba(src), "5\n")

    def test_typed_rejects_wrong_arg(self):
        src = (
            "@typed\n"
            "def add(x: int, y: int) -> int:\n"
            "    return x + y\n"
            "add('a', 1)\n"
        )
        with self.assertRaises(TypeError):
            run_mamba(src)

    def test_typed_rejects_wrong_return(self):
        src = (
            "@typed\n"
            "def liar(x: int) -> str:\n"
            "    return x\n"
            "liar(5)\n"
        )
        with self.assertRaises(TypeError):
            run_mamba(src)

    def test_typed_skips_unannotated_params(self):
        src = (
            "@typed\n"
            "def f(x: int, y) -> int:\n"
            "    return x\n"
            "print(f(5, 'whatever'))\n"
        )
        self.assertEqual(run_mamba(src), "5\n")

    def test_typed_user_class_with_mro(self):
        src = (
            "class Animal:\n"
            "    pass\n"
            "class Dog(Animal):\n"
            "    pass\n"
            "@typed\n"
            "def feed(a: Animal) -> str:\n"
            "    return 'fed'\n"
            "print(feed(Dog()))\n"
        )
        self.assertEqual(run_mamba(src), "fed\n")

    def test_typed_rejects_non_subclass(self):
        src = (
            "class Animal:\n"
            "    pass\n"
            "@typed\n"
            "def feed(a: Animal) -> str:\n"
            "    return 'fed'\n"
            "feed('woof')\n"
        )
        with self.assertRaises(TypeError):
            run_mamba(src)

    def test_typed_keyword_arg_check(self):
        src = (
            "@typed\n"
            "def f(x: int, y: int) -> int:\n"
            "    return x + y\n"
            "f(x=2, y='nope')\n"
        )
        with self.assertRaises(TypeError):
            run_mamba(src)


if __name__ == "__main__":
    unittest.main()
