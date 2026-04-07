"""Error types for Mamba with Elm/Rust-style formatted output."""

import os
import sys


def _levenshtein(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            curr[j] = min(
                curr[j - 1] + 1,
                prev[j] + 1,
                prev[j - 1] + (ca != cb),
            )
        prev = curr
    return prev[-1]


def suggest(name, candidates, max_distance=None):
    """Return the closest candidate to `name`, or None if nothing's close."""
    if not name:
        return None
    if max_distance is None:
        # Allow ~1/3 of the name length, minimum 1
        max_distance = max(1, len(name) // 3)
    best = None
    best_d = max_distance + 1
    for c in candidates:
        if not c or c == name:
            continue
        d = _levenshtein(name, c)
        if d < best_d:
            best_d = d
            best = c
    return best


def _supports_color():
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("MAMBA_NO_COLOR"):
        return False
    return sys.stderr.isatty() if hasattr(sys.stderr, "isatty") else False


class _Style:
    def __init__(self, enabled):
        self.RED = "\033[31m" if enabled else ""
        self.BOLD_RED = "\033[1;31m" if enabled else ""
        self.YELLOW = "\033[33m" if enabled else ""
        self.CYAN = "\033[36m" if enabled else ""
        self.DIM = "\033[2m" if enabled else ""
        self.BOLD = "\033[1m" if enabled else ""
        self.RESET = "\033[0m" if enabled else ""


class MambaError(Exception):
    """Base error for all Mamba-level problems (lex/parse/runtime)."""

    KIND = "Error"

    def __init__(self, message, line=None, col=None, file=None, source=None,
                 hint=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        self.file = file
        self.source = source
        self.hint = hint

    def format(self, color=None) -> str:
        if color is None:
            color = _supports_color()
        s = _Style(color)
        loc = self.file or "<source>"
        if self.line is not None:
            loc += f":{self.line}"
            if self.col is not None:
                loc += f":{self.col}"

        # Header — bold red box-style title
        title = self.KIND.upper()
        head = f"{s.BOLD_RED}-- {title} {'-' * max(2, 60 - len(title))}{s.RESET}"
        out = [head, ""]
        out.append(f"{s.RED}{self.message}{s.RESET}")
        out.append(f"{s.DIM}  --> {loc}{s.RESET}")
        out.append("")

        # Source context: line ±2 with gutter
        if self.source and self.line is not None:
            lines = self.source.splitlines()
            if 1 <= self.line <= len(lines):
                start = max(1, self.line - 2)
                end = min(len(lines), self.line + 2)
                width = len(str(end))
                for n in range(start, end + 1):
                    gutter = str(n).rjust(width)
                    text = lines[n - 1]
                    if n == self.line:
                        out.append(
                            f"{s.CYAN}{gutter} |{s.RESET} "
                            f"{s.BOLD}{text}{s.RESET}"
                        )
                        if self.col is not None and self.col >= 1:
                            pad = " " * (self.col - 1)
                            out.append(
                                f"{s.CYAN}{' ' * width} |{s.RESET} "
                                f"{pad}{s.BOLD_RED}^{s.RESET}"
                            )
                    else:
                        out.append(
                            f"{s.DIM}{gutter} | {text}{s.RESET}"
                        )
                out.append("")

        if self.hint:
            out.append(f"{s.YELLOW}help:{s.RESET} {self.hint}")
            out.append("")

        return "\n".join(out)

    def __str__(self):
        return self.format(color=False)


class MambaSyntaxError(MambaError):
    KIND = "Syntax Error"


class MambaRuntimeError(MambaError):
    KIND = "Runtime Error"
