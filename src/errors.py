"""Error types for Mamba with Elm/Rust-style formatted output."""

import os
import sys


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
