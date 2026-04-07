"""Mamba's built-in package manager.

The honest scope: pip already solves the hard problem of fetching wheels and
resolving dependencies from PyPI. What pip *doesn't* solve well is the
ergonomics — every Python project starts with the same boring dance of
`python -m venv`, `source venv/bin/activate`, `pip install`, `pip freeze`,
`requirements.txt`. Mamba's package manager is a thin layer that gives you
what `npm` gives JavaScript: a project-local module directory and a manifest
file, with no virtualenv ritual.

Layout:

    your_project/
        mamba.json           ← manifest
        mamba_modules/       ← project-local installs (like node_modules)
        main.py

Commands:

    mamba init               create a fresh mamba.json
    mamba add requests       install + record in manifest
    mamba remove requests    uninstall + drop from manifest
    mamba install            install everything in the manifest

When the Mamba interpreter runs a file, it automatically inserts the
project's `mamba_modules/` into `sys.path`, so `import requests` just works.
"""

import json
import os
import subprocess
import sys


MANIFEST_NAME = "mamba.json"
MODULES_DIR = "mamba_modules"


# ---------- manifest ----------

def find_manifest(start=None):
    """Walk upward from `start` looking for the nearest mamba.json. Returns
    the absolute path or None."""
    cur = os.path.abspath(start or os.getcwd())
    while True:
        candidate = os.path.join(cur, MANIFEST_NAME)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def load_manifest(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_manifest(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def empty_manifest(name="my-mamba-project"):
    return {
        "name": name,
        "version": "0.1.0",
        "dependencies": {},
    }


def project_root_for(manifest_path):
    return os.path.dirname(os.path.abspath(manifest_path))


def modules_path_for(manifest_path):
    return os.path.join(project_root_for(manifest_path), MODULES_DIR)


# ---------- commands ----------

def cmd_init(cwd=None):
    cwd = cwd or os.getcwd()
    path = os.path.join(cwd, MANIFEST_NAME)
    if os.path.exists(path):
        print(f"mamba: {MANIFEST_NAME} already exists in {cwd}")
        return 1
    save_manifest(path, empty_manifest(os.path.basename(cwd)))
    print(f"mamba: created {path}")
    return 0


def cmd_add(pkg, cwd=None, runner=None):
    """Install `pkg` into ./mamba_modules and record it in the manifest.
    `runner` is an injection point for tests — defaults to real pip."""
    cwd = cwd or os.getcwd()
    manifest_path = find_manifest(cwd) or os.path.join(cwd, MANIFEST_NAME)
    if not os.path.exists(manifest_path):
        save_manifest(manifest_path, empty_manifest(os.path.basename(cwd)))
    data = load_manifest(manifest_path)
    target = modules_path_for(manifest_path)
    code = (runner or _pip_install)(pkg, target)
    if code != 0:
        print(f"mamba: failed to install {pkg!r} (pip exit code {code})")
        return code
    data.setdefault("dependencies", {})[pkg] = "*"
    save_manifest(manifest_path, data)
    print(f"mamba: added {pkg} → {os.path.relpath(target)}")
    return 0


def cmd_remove(pkg, cwd=None, runner=None):
    cwd = cwd or os.getcwd()
    manifest_path = find_manifest(cwd)
    if manifest_path is None:
        print(f"mamba: no {MANIFEST_NAME} found")
        return 1
    data = load_manifest(manifest_path)
    deps = data.get("dependencies", {})
    if pkg not in deps:
        print(f"mamba: {pkg!r} is not in dependencies")
        return 1
    target = modules_path_for(manifest_path)
    code = (runner or _pip_uninstall)(pkg, target)
    deps.pop(pkg, None)
    save_manifest(manifest_path, data)
    print(f"mamba: removed {pkg}")
    return code


def cmd_install(cwd=None, runner=None):
    """Install every dep in the manifest into ./mamba_modules."""
    cwd = cwd or os.getcwd()
    manifest_path = find_manifest(cwd)
    if manifest_path is None:
        print(f"mamba: no {MANIFEST_NAME} found")
        return 1
    data = load_manifest(manifest_path)
    deps = data.get("dependencies", {})
    if not deps:
        print("mamba: nothing to install")
        return 0
    target = modules_path_for(manifest_path)
    install = runner or _pip_install
    for name in deps:
        code = install(name, target)
        if code != 0:
            print(f"mamba: failed installing {name!r}, aborting")
            return code
    print(f"mamba: installed {len(deps)} package(s) into "
          f"{os.path.relpath(target)}")
    return 0


# ---------- interpreter integration ----------

def inject_modules_path(start_file):
    """If the file being run sits in (or under) a Mamba project, prepend
    that project's mamba_modules/ to sys.path so imports resolve."""
    manifest = find_manifest(os.path.dirname(os.path.abspath(start_file)))
    if manifest is None:
        return
    target = modules_path_for(manifest)
    if os.path.isdir(target) and target not in sys.path:
        sys.path.insert(0, target)


# ---------- pip shell-out ----------

def _pip_install(pkg, target):
    return subprocess.call(
        [sys.executable, "-m", "pip", "install",
         "--quiet", "--target", target, pkg]
    )


def _pip_uninstall(pkg, target):
    # pip's uninstall doesn't understand --target, so just remove the
    # package directory directly. This mirrors what npm does.
    import shutil
    pkg_dir = os.path.join(target, pkg)
    if os.path.isdir(pkg_dir):
        shutil.rmtree(pkg_dir)
    # also nuke any *.dist-info that matches
    if os.path.isdir(target):
        for entry in os.listdir(target):
            if (entry.startswith(pkg + "-")
                    and entry.endswith(".dist-info")):
                shutil.rmtree(os.path.join(target, entry))
    return 0
