# Mamba 🐍

A Python interpreter written in Python. Long-term goal: run real `.py` files
the same way CPython would.

## Status

**Work in progress.** Currently only the lexer is implemented. The interpreter
is being built bottom-up: lexer → parser → AST evaluator → scoping/functions →
classes → exceptions → modules → builtins → stdlib.

### What's done

- **Lexer** (`src/lexer.py`): tokenizes Python source.
  - Numbers (int, float), strings, names
  - Operators: `+ - * / = == != < > <= >=`
  - Delimiters: `( ) [ ] { } , . :`
  - Keywords: `if elif else while for in def return pass break continue and or not True False None`
  - `INDENT` / `DEDENT` with an indentation stack
  - Newlines suppressed inside `() [] {}`
  - Comments (`#`) and line continuation (`\`)

### Next up

- Parser → AST
- Tree-walking evaluator (subset)
- Scoping and function calls
- `tests/` with CPython as oracle (run a `.py` in both, compare output)

## Project layout

```
Mamba/
├── main.py          # CLI entry point (file runner + REPL)
├── examples/
│   └── hello.py     # Sample Python program the lexer can chew on
├── src/
│   ├── lexer.py
│   └── errors.py    # (WIP)
└── README.md
```

## Running

```bash
python3 main.py examples/hello.py   # tokenize a file
python3 main.py                     # REPL
```
