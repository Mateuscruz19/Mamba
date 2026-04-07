"""Phase J tests: built-in package manager.

These tests exercise manifest read/write, the add/remove/install command
flow, and the interpreter integration that injects ./mamba_modules into
sys.path. They use a fake `runner` so no real network calls happen."""

import json
import os
import sys
import tempfile
import unittest

from src import pkg


class FakeRunner:
    """Stand-in for pip. Records every (pkg, target) pair it was asked to
    install and creates a stub directory so the install looks real."""

    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on or set()

    def install(self, name, target):
        self.calls.append((name, target))
        if name in self.fail_on:
            return 1
        os.makedirs(os.path.join(target, name), exist_ok=True)
        with open(os.path.join(target, name, "__init__.py"), 'w') as f:
            f.write(f"# fake {name}\n")
        return 0

    def uninstall(self, name, target):
        import shutil
        d = os.path.join(target, name)
        if os.path.isdir(d):
            shutil.rmtree(d)
        return 0


class ManifestTests(unittest.TestCase):
    def test_empty_manifest_shape(self):
        m = pkg.empty_manifest("demo")
        self.assertEqual(m["name"], "demo")
        self.assertEqual(m["dependencies"], {})
        self.assertIn("version", m)

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, pkg.MANIFEST_NAME)
            pkg.save_manifest(path, {"name": "x", "dependencies": {"a": "*"}})
            data = pkg.load_manifest(path)
            self.assertEqual(data["dependencies"], {"a": "*"})

    def test_find_manifest_walks_upward(self):
        with tempfile.TemporaryDirectory() as d:
            pkg.save_manifest(os.path.join(d, pkg.MANIFEST_NAME),
                              pkg.empty_manifest("x"))
            nested = os.path.join(d, "deep", "deeper")
            os.makedirs(nested)
            found = pkg.find_manifest(nested)
            self.assertEqual(os.path.dirname(found), d)


class CommandTests(unittest.TestCase):
    def test_init_creates_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            code = pkg.cmd_init(cwd=d)
            self.assertEqual(code, 0)
            self.assertTrue(os.path.isfile(os.path.join(d, pkg.MANIFEST_NAME)))

    def test_init_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            pkg.cmd_init(cwd=d)
            code = pkg.cmd_init(cwd=d)
            self.assertEqual(code, 1)

    def test_add_records_dep_and_invokes_runner(self):
        with tempfile.TemporaryDirectory() as d:
            r = FakeRunner()
            code = pkg.cmd_add("requests", cwd=d, runner=r.install)
            self.assertEqual(code, 0)
            data = pkg.load_manifest(os.path.join(d, pkg.MANIFEST_NAME))
            self.assertIn("requests", data["dependencies"])
            self.assertEqual(len(r.calls), 1)
            self.assertEqual(r.calls[0][0], "requests")

    def test_add_failure_doesnt_record(self):
        with tempfile.TemporaryDirectory() as d:
            r = FakeRunner(fail_on={"badpkg"})
            code = pkg.cmd_add("badpkg", cwd=d, runner=r.install)
            self.assertNotEqual(code, 0)
            data = pkg.load_manifest(os.path.join(d, pkg.MANIFEST_NAME))
            self.assertNotIn("badpkg", data["dependencies"])

    def test_remove_drops_dep(self):
        with tempfile.TemporaryDirectory() as d:
            r = FakeRunner()
            pkg.cmd_add("foo", cwd=d, runner=r.install)
            code = pkg.cmd_remove("foo", cwd=d, runner=r.uninstall)
            self.assertEqual(code, 0)
            data = pkg.load_manifest(os.path.join(d, pkg.MANIFEST_NAME))
            self.assertNotIn("foo", data["dependencies"])

    def test_install_runs_every_dep(self):
        with tempfile.TemporaryDirectory() as d:
            pkg.save_manifest(
                os.path.join(d, pkg.MANIFEST_NAME),
                {"name": "x", "version": "0", "dependencies": {
                    "a": "*", "b": "*", "c": "*",
                }}
            )
            r = FakeRunner()
            code = pkg.cmd_install(cwd=d, runner=r.install)
            self.assertEqual(code, 0)
            self.assertEqual({c[0] for c in r.calls}, {"a", "b", "c"})


class IntegrationTests(unittest.TestCase):
    def test_inject_modules_path_adds_to_syspath(self):
        with tempfile.TemporaryDirectory() as d:
            pkg.save_manifest(os.path.join(d, pkg.MANIFEST_NAME),
                              pkg.empty_manifest("x"))
            os.makedirs(os.path.join(d, pkg.MODULES_DIR))
            file_in_project = os.path.join(d, "main.py")
            open(file_in_project, 'w').close()

            saved = list(sys.path)
            try:
                pkg.inject_modules_path(file_in_project)
                self.assertTrue(
                    any(p.endswith(pkg.MODULES_DIR) for p in sys.path),
                    f"mamba_modules not in sys.path: {sys.path}"
                )
            finally:
                sys.path[:] = saved


if __name__ == "__main__":
    unittest.main()
