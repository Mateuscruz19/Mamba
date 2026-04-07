import os
import sys

from src.lexer import Lexer
from src.parser import Parser
from src.interpreter import Interpreter
from src.errors import MambaError
from src import ast_nodes as ast


def run_file(path: str) -> None:
    with open(path, 'r', encoding='utf-8') as f:
        source = f.read()
    try:
        tokens = Lexer(source).tokenize()
        tree = Parser(tokens, source=source, file=path).parse()
        Interpreter(file=os.path.abspath(path)).run(tree)
    except MambaError as e:
        print(e.format(), file=sys.stderr)
        sys.exit(1)


def repl() -> None:
    print("Mamba REPL — Ctrl+D to exit")
    interp = Interpreter()
    try:
        while True:
            line = input(">>> ")
            stripped = line.strip()
            if not stripped:
                continue
            try:
                tokens = Lexer(stripped + "\n").tokenize()
                tree = Parser(tokens, source=stripped).parse()
                # If the line is a single bare expression, print its value
                # the way a normal REPL does.
                if (len(tree.body) == 1
                        and isinstance(tree.body[0], ast.ExprStmt)):
                    value = interp.eval_expr(tree.body[0].expr, interp.globals)
                    if value is not None:
                        print(repr(value))
                else:
                    interp.run(tree)
            except MambaError as e:
                print(e.format())
            except Exception as e:
                print(f"{type(e).__name__}: {e}")
    except EOFError:
        print()


def main() -> None:
    if len(sys.argv) > 1:
        run_file(sys.argv[1])
    else:
        repl()


if __name__ == "__main__":
    main()
