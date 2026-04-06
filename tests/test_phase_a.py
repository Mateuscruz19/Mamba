"""Phase A tests: LEGB scoping, iterator protocol, operator dunders,
container dunders, and 'in' / 'not in'."""

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


class ScopeTests(unittest.TestCase):
    def test_global(self):
        src = (
            "counter = 0\n"
            "def inc():\n"
            "    global counter\n"
            "    counter += 1\n"
            "inc()\ninc()\ninc()\n"
            "print(counter)\n"
        )
        assert_matches_cpython(self, src)

    def test_nonlocal(self):
        src = (
            "def make():\n"
            "    n = 0\n"
            "    def add(x):\n"
            "        nonlocal n\n"
            "        n += x\n"
            "        return n\n"
            "    return add\n"
            "a = make()\n"
            "print(a(5))\n"
            "print(a(10))\n"
        )
        assert_matches_cpython(self, src)

    def test_assignment_creates_local(self):
        # Without nonlocal, assigning x in inner shouldn't touch outer x
        src = (
            "def f():\n"
            "    x = 1\n"
            "    def g():\n"
            "        x = 99\n"
            "    g()\n"
            "    return x\n"
            "print(f())\n"
        )
        assert_matches_cpython(self, src)

    def test_global_from_nested(self):
        src = (
            "g = 1\n"
            "def outer():\n"
            "    def inner():\n"
            "        global g\n"
            "        g = 42\n"
            "    inner()\n"
            "outer()\n"
            "print(g)\n"
        )
        assert_matches_cpython(self, src)


class IteratorProtocolTests(unittest.TestCase):
    def test_user_iterator(self):
        src = (
            "class R:\n"
            "    def __init__(self, n):\n"
            "        self.n = n\n"
            "        self.i = 0\n"
            "    def __iter__(self):\n"
            "        return self\n"
            "    def __next__(self):\n"
            "        if self.i >= self.n:\n"
            "            raise StopIteration\n"
            "        v = self.i\n"
            "        self.i += 1\n"
            "        return v\n"
            "print(list(R(4)))\n"
            "for x in R(3):\n"
            "    print(x)\n"
        )
        self.assertEqual(run_mamba(src), "[0, 1, 2, 3]\n0\n1\n2\n")

    def test_iter_next_builtins(self):
        src = "it = iter([10, 20, 30])\nprint(next(it))\nprint(next(it))\n"
        assert_matches_cpython(self, src)


class OperatorDunderTests(unittest.TestCase):
    def test_arith_dunders(self):
        src = (
            "class V:\n"
            "    def __init__(self, n):\n"
            "        self.n = n\n"
            "    def __add__(self, o):\n"
            "        return V(self.n + o.n)\n"
            "    def __mul__(self, k):\n"
            "        return V(self.n * k)\n"
            "    def __repr__(self):\n"
            "        return f'V({self.n})'\n"
            "print(V(2) + V(3))\n"
            "print(V(4) * 5)\n"
        )
        self.assertEqual(run_mamba(src), "V(5)\nV(20)\n")

    def test_comparison_dunders(self):
        src = (
            "class N:\n"
            "    def __init__(self, v):\n"
            "        self.v = v\n"
            "    def __lt__(self, o):\n"
            "        return self.v < o.v\n"
            "    def __eq__(self, o):\n"
            "        return self.v == o.v\n"
            "    def __repr__(self):\n"
            "        return str(self.v)\n"
            "xs = [N(3), N(1), N(2)]\n"
            "print(sorted(xs))\n"
            "print(N(1) == N(1))\n"
        )
        self.assertEqual(run_mamba(src), "[1, 2, 3]\nTrue\n")

    def test_neg_dunder(self):
        src = (
            "class N:\n"
            "    def __init__(self, v):\n"
            "        self.v = v\n"
            "    def __neg__(self):\n"
            "        return N(-self.v)\n"
            "    def __repr__(self):\n"
            "        return str(self.v)\n"
            "print(-N(5))\n"
        )
        self.assertEqual(run_mamba(src), "-5\n")


class ContainerDunderTests(unittest.TestCase):
    def test_getitem_setitem(self):
        src = (
            "class B:\n"
            "    def __init__(self):\n"
            "        self.d = {}\n"
            "    def __getitem__(self, k):\n"
            "        return self.d[k]\n"
            "    def __setitem__(self, k, v):\n"
            "        self.d[k] = v\n"
            "b = B()\n"
            "b['x'] = 10\n"
            "print(b['x'])\n"
        )
        self.assertEqual(run_mamba(src), "10\n")

    def test_len_bool_contains(self):
        src = (
            "class B:\n"
            "    def __init__(self):\n"
            "        self.d = [1,2,3]\n"
            "    def __len__(self):\n"
            "        return len(self.d)\n"
            "    def __contains__(self, k):\n"
            "        return k in self.d\n"
            "b = B()\n"
            "print(len(b))\n"
            "print(2 in b)\n"
            "print(5 in b)\n"
            "print(5 not in b)\n"
            "if b:\n"
            "    print('truthy')\n"
        )
        self.assertEqual(run_mamba(src), "3\nTrue\nFalse\nTrue\ntruthy\n")

    def test_call_dunder(self):
        src = (
            "class Doubler:\n"
            "    def __call__(self, x):\n"
            "        return x * 2\n"
            "d = Doubler()\n"
            "print(d(21))\n"
        )
        self.assertEqual(run_mamba(src), "42\n")


class InOperatorTests(unittest.TestCase):
    def test_list_in(self):
        assert_matches_cpython(self, "print(3 in [1,2,3])\nprint(5 not in [1,2,3])\n")

    def test_dict_in(self):
        assert_matches_cpython(self, "print('a' in {'a': 1})\n")

    def test_string_in(self):
        assert_matches_cpython(self, "print('mb' in 'mamba')\n")


if __name__ == "__main__":
    unittest.main()
