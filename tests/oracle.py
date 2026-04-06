"""CLI test runner: runs every tests/cases/*.py through Mamba and CPython,
diffing the outputs. Exit code is non-zero if any case mismatches."""

import os
import subprocess
import sys


def main():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cases_dir = os.path.join(repo, "tests", "cases")
    cases = sorted(
        os.path.join(cases_dir, f)
        for f in os.listdir(cases_dir)
        if f.endswith(".py")
    )

    failed = 0
    for path in cases:
        name = os.path.basename(path)
        mamba = subprocess.run(
            ["python3", "main.py", path],
            cwd=repo, capture_output=True, text=True,
        )
        cpython = subprocess.run(
            ["python3", path],
            cwd=repo, capture_output=True, text=True,
        )
        if mamba.stdout == cpython.stdout and mamba.returncode == 0:
            print(f"  ok    {name}")
        else:
            failed += 1
            print(f"  FAIL  {name}")
            if mamba.returncode != 0:
                print(f"    mamba exited {mamba.returncode}")
                print(f"    stderr: {mamba.stderr.strip()}")
            else:
                print("    --- mamba ---")
                print("    " + mamba.stdout.replace("\n", "\n    "))
                print("    --- cpython ---")
                print("    " + cpython.stdout.replace("\n", "\n    "))

    total = len(cases)
    print()
    print(f"{total - failed}/{total} cases passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
