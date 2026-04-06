# Mamba 🐍

A custom programming language built from scratch in Python.

## Status

**Work in progress** — currently in the early stages of development.

### What's done so far

- **Lexer** (`src/lexer.py`): Tokenizes source code into a stream of tokens. Supports:
  - Numbers (integers and floats)
  - Strings (single and double quoted)
  - Names/identifiers
  - Operators: `+`, `-`, `*`, `/`, `=`
  - Delimiters: `(`, `)`, `:`
  - Newlines as significant tokens

### What's next

- Parser (AST generation)
- Interpreter / code execution
- Keywords and control flow (`if`, `while`, `def`, etc.)
- Error handling system

## Project Structure

```
Mamba/
├── main.py          # Entry point
├── src/
│   ├── lexer.py     # Tokenizer / lexical analysis
│   └── errors.py    # Error handling (WIP)
└── README.md
```

## Running

```bash
python main.py
```
