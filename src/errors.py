"""Error types for Mamba with location info and source snippets."""


class MambaError(Exception):
    """Base error for all Mamba-level problems (lex/parse/runtime)."""

    def __init__(self, message, line=None, col=None, file=None, source=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        self.file = file
        self.source = source

    def format(self) -> str:
        parts = []
        loc = self.file or "<source>"
        if self.line is not None:
            loc += f":{self.line}"
            if self.col is not None:
                loc += f":{self.col}"
        parts.append(f"{type(self).__name__}: {self.message}")
        parts.append(f"  at {loc}")
        if self.source and self.line is not None:
            lines = self.source.splitlines()
            if 1 <= self.line <= len(lines):
                snippet = lines[self.line - 1]
                parts.append(f"  | {snippet}")
                if self.col is not None:
                    parts.append("  | " + " " * (self.col - 1) + "^")
        return "\n".join(parts)

    def __str__(self):
        return self.format()


class MambaSyntaxError(MambaError):
    pass


class MambaRuntimeError(MambaError):
    pass
