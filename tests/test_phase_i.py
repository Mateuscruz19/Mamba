"""Phase I tests: structured concurrency.

spawn / parallel / nursery run on real OS threads. CPU-bound workloads
still serialize on CPython's GIL, but I/O-bound workloads parallelize and
the API is the part that matters here — it should remain identical when a
free-threaded backend lands."""

import io
import time
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


class SpawnAndJoinTests(unittest.TestCase):
    def test_spawn_returns_value_via_join(self):
        src = (
            "def double(x):\n"
            "    return x * 2\n"
            "t = spawn(double, 21)\n"
            "print(t.join())\n"
        )
        self.assertEqual(run_mamba(src), "42\n")

    def test_join_reraises_task_error(self):
        src = (
            "def boom():\n"
            "    raise ValueError('nope')\n"
            "t = spawn(boom)\n"
            "t.join()\n"
        )
        with self.assertRaises(ValueError):
            run_mamba(src)

    def test_done_flag(self):
        src = (
            "def quick():\n"
            "    return 1\n"
            "t = spawn(quick)\n"
            "t.join()\n"
            "print(t.done())\n"
        )
        self.assertEqual(run_mamba(src), "True\n")


class ParallelTests(unittest.TestCase):
    def test_parallel_returns_results_in_order(self):
        src = (
            "results = parallel(\n"
            "    lambda: 1,\n"
            "    lambda: 2,\n"
            "    lambda: 3,\n"
            ")\n"
            "print(results)\n"
        )
        self.assertEqual(run_mamba(src), "[1, 2, 3]\n")

    def test_parallel_actually_runs_concurrently_for_io(self):
        # All four sleeps run on threads, so wall time should be much closer
        # to one sleep than to four. Use a generous threshold to avoid
        # flakiness on slow CI.
        src = (
            "def waited():\n"
            "    sleep(0.1)\n"
            "    return 1\n"
            "results = parallel(waited, waited, waited, waited)\n"
            "print(sum(results))\n"
        )
        start = time.monotonic()
        out = run_mamba(src)
        elapsed = time.monotonic() - start
        self.assertEqual(out, "4\n")
        self.assertLess(elapsed, 0.35,
                        f"parallel sleeps took {elapsed:.2f}s, expected ~0.1s")

    def test_parallel_accepts_list(self):
        src = (
            "fns = [lambda: 'a', lambda: 'b', lambda: 'c']\n"
            "print(parallel(fns))\n"
        )
        self.assertEqual(run_mamba(src), "['a', 'b', 'c']\n")


class NurseryTests(unittest.TestCase):
    def test_nursery_auto_joins(self):
        src = (
            "log = []\n"
            "def push(x):\n"
            "    log.append(x)\n"
            "with nursery() as n:\n"
            "    n.spawn(push, 1)\n"
            "    n.spawn(push, 2)\n"
            "    n.spawn(push, 3)\n"
            "print(sorted(log))\n"
        )
        self.assertEqual(run_mamba(src), "[1, 2, 3]\n")

    def test_nursery_propagates_error(self):
        src = (
            "def boom():\n"
            "    raise ValueError('x')\n"
            "with nursery() as n:\n"
            "    n.spawn(boom)\n"
        )
        with self.assertRaises(ValueError):
            run_mamba(src)

    def test_nursery_waits_for_all_before_raising(self):
        src = (
            "log = []\n"
            "def slow_ok():\n"
            "    sleep(0.05)\n"
            "    log.append('ok')\n"
            "def boom():\n"
            "    raise ValueError('x')\n"
            "try:\n"
            "    with nursery() as n:\n"
            "        n.spawn(slow_ok)\n"
            "        n.spawn(boom)\n"
            "except ValueError:\n"
            "    pass\n"
            "print(log)\n"
        )
        self.assertEqual(run_mamba(src), "['ok']\n")


if __name__ == "__main__":
    unittest.main()
