"""Phase B tests: decorators, staticmethod/classmethod/property,
C3 MRO + super(), and metaclasses."""

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


class DecoratorTests(unittest.TestCase):
    def test_function_decorator(self):
        src = (
            "def deco(f):\n"
            "    def w(x):\n"
            "        return f(x) + 1\n"
            "    return w\n"
            "@deco\n"
            "def g(x):\n"
            "    return x * 2\n"
            "print(g(10))\n"
        )
        assert_matches_cpython(self, src)

    def test_stacked_decorators(self):
        # right-to-left application
        src = (
            "def add1(f):\n"
            "    def w(x):\n"
            "        return f(x) + 1\n"
            "    return w\n"
            "def mul2(f):\n"
            "    def w(x):\n"
            "        return f(x) * 2\n"
            "    return w\n"
            "@add1\n"
            "@mul2\n"
            "def g(x):\n"
            "    return x\n"
            "print(g(5))\n"  # mul2 first -> 10, then add1 -> 11
        )
        assert_matches_cpython(self, src)

    def test_class_decorator(self):
        src = (
            "def rename(cls):\n"
            "    return 'WRAPPED'\n"
            "@rename\n"
            "class C:\n"
            "    pass\n"
            "print(C)\n"
        )
        self.assertEqual(run_mamba(src), "WRAPPED\n")


class DescriptorTests(unittest.TestCase):
    def test_staticmethod(self):
        src = (
            "class C:\n"
            "    @staticmethod\n"
            "    def s(x):\n"
            "        return x + 1\n"
            "print(C.s(10))\n"
            "print(C().s(20))\n"
        )
        assert_matches_cpython(self, src)

    def test_classmethod(self):
        # cls is bound to the class — verify by mutating shared state
        src = (
            "log = []\n"
            "class C:\n"
            "    @classmethod\n"
            "    def make(cls, x):\n"
            "        log.append(x)\n"
            "        return x + 1\n"
            "print(C.make(7))\n"
            "print(C().make(8))\n"
            "print(log)\n"
        )
        self.assertEqual(run_mamba(src), "8\n9\n[7, 8]\n")

    def test_property_get(self):
        src = (
            "class C:\n"
            "    def __init__(self, v):\n"
            "        self._v = v\n"
            "    @property\n"
            "    def v(self):\n"
            "        return self._v\n"
            "print(C(42).v)\n"
        )
        assert_matches_cpython(self, src)

    def test_property_setter(self):
        src = (
            "class C:\n"
            "    def __init__(self, v):\n"
            "        self._v = v\n"
            "    @property\n"
            "    def v(self):\n"
            "        return self._v\n"
            "    @v.setter\n"
            "    def v(self, val):\n"
            "        self._v = val * 2\n"
            "o = C(7)\n"
            "print(o.v)\n"
            "o.v = 4\n"
            "print(o.v)\n"
        )
        self.assertEqual(run_mamba(src), "7\n8\n")


class MROAndSuperTests(unittest.TestCase):
    def test_diamond_super(self):
        src = (
            "class A:\n"
            "    def hi(self):\n"
            "        return 'A'\n"
            "class B(A):\n"
            "    def hi(self):\n"
            "        return 'B->' + super().hi()\n"
            "class C(A):\n"
            "    def hi(self):\n"
            "        return 'C->' + super().hi()\n"
            "class D(B, C):\n"
            "    def hi(self):\n"
            "        return 'D->' + super().hi()\n"
            "print(D().hi())\n"
        )
        # C3 linearization: D -> B -> C -> A
        self.assertEqual(run_mamba(src), "D->B->C->A\n")

    def test_super_init_chain(self):
        src = (
            "class Animal:\n"
            "    def __init__(self, name):\n"
            "        self.name = name\n"
            "class Dog(Animal):\n"
            "    def __init__(self, name, breed):\n"
            "        super().__init__(name)\n"
            "        self.breed = breed\n"
            "d = Dog('Rex', 'lab')\n"
            "print(d.name, d.breed)\n"
        )
        assert_matches_cpython(self, src)

    def test_three_level_super(self):
        src = (
            "class A:\n"
            "    def f(self):\n"
            "        return 1\n"
            "class B(A):\n"
            "    def f(self):\n"
            "        return super().f() + 10\n"
            "class C(B):\n"
            "    def f(self):\n"
            "        return super().f() + 100\n"
            "print(C().f())\n"
        )
        assert_matches_cpython(self, src)


class MetaclassTests(unittest.TestCase):
    def test_function_metaclass(self):
        src = (
            "def meta(name, bases, attrs):\n"
            "    return 'TAG:' + name\n"
            "class Foo(metaclass=meta):\n"
            "    x = 1\n"
            "print(Foo)\n"
        )
        self.assertEqual(run_mamba(src), "TAG:Foo\n")

    def test_metaclass_sees_attrs(self):
        src = (
            "captured = {}\n"
            "def meta(name, bases, attrs):\n"
            "    captured['name'] = name\n"
            "    captured['has_x'] = 'x' in attrs\n"
            "    return name\n"
            "class Foo(metaclass=meta):\n"
            "    x = 42\n"
            "print(captured['name'], captured['has_x'])\n"
        )
        self.assertEqual(run_mamba(src), "Foo True\n")


if __name__ == "__main__":
    unittest.main()
