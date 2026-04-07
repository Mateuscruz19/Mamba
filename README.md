<p align="center">
  <img src="assets/logo.png" alt="Mamba" width="240">
</p>

<h1 align="center" style="color:#a3d977">Mamba</h1>

<p align="center">
  <em>A Python-compatible language with the features Python users always wanted.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-a3d977?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/tests-183%20passing-a3d977" alt="Tests">
  <img src="https://img.shields.io/badge/status-experimental-1b1f23" alt="Status">
  <img src="https://img.shields.io/badge/license-MIT-1b1f23" alt="License">
  <img src="https://img.shields.io/badge/built%20with-tree--walking-a3d977" alt="Tree-walking interpreter">
</p>

---

## What is Mamba?

**Mamba** is a Python interpreter written in Python — but it is *not* trying
to be a 1:1 CPython clone. The goal is to be **Python-compatible enough** to
run real-world scripts while shipping the language features the community has
been asking for and never got.

Think **Discord vs Skype**: same category, win by being better.

```python
# This is a valid Mamba program.
@memo
def fib(n):
    if n < 2:
        return n
    return fib(n-1) + fib(n-2)

users = [{"name": "ada", "age": 36}, {"name": "linus", "age": 54}]
adults = users |> filter(lambda u: u["age"] >= 18) |> list

config = load_config()
host = config?.server?.host ?? "localhost"

label = match status {
    200 => "ok",
    404 => "not found",
    _   => "weird"
}
```

## Why Mamba

CPython is great. It's also slow to evolve, allergic to syntax changes, and
ships with tooling that everyone has opinions about. Mamba says yes to the
small, boring features Python keeps rejecting:

- A real **pipe operator** (`|>`)
- **Null-coalescing** and **optional chaining** (`??`, `?.`, `?[`)
- **Pattern matching as an expression** (`match { ... }`)
- **Block lambdas** that span multiple lines
- **Block comments** (`/* ... */`)
- **Real runtime function overloading** — not just a typing hint
- **Elm-style error messages** with caret + suggestions + "did you mean?"
- The mutable-default-argument footgun, **fixed**

## Quick start

Mamba is pure Python — no compilation, no native dependencies.

```bash
git clone https://github.com/Mateuscruz19/Mamba.git
cd Mamba

# Run a file
python3 main.py examples/showcase.py

# Open a REPL
python3 main.py
```

Requires Python 3.10+.

## Feature tour

### Pipe operator `|>`

Append-by-default to match Python's stdlib (`map(fn, iter)`), with `_` as an
explicit placeholder when you need to put the value somewhere else:

```python
[1, 2, 3, 4, 5] |> map(lambda x: x*x) |> list      # [1, 4, 9, 16, 25]
"  hi  " |> str.strip |> str.upper                  # "HI"
10 |> sub(_, 3)                                     # 7
10 |> sub(3, _)                                     # -7
```

### Null-coalescing `??`

Returns the left side if it isn't `None`, otherwise the right. Short-circuits
the right side and **does not** treat `0`, `""`, or `[]` as missing:

```python
name = user_name ?? "anonymous"
0 ?? 99           # 0  — falsy but not None
None ?? 99        # 99
```

### Optional chaining `?.` and `?[`

Once any link in the chain is `None` (or hits a missing attribute / key),
the **entire rest of the chain** short-circuits to `None` — TS/Swift style:

```python
city = user?.address?.city                       # None instead of crash
first_tag = post?.tags?[0]                       # None if tags missing
host = config?.server?.host ?? "localhost"
```

### `match` expression

```python
def describe(n):
    return match n {
        0 => "zero",
        1 => "one",
        2 => "two",
        _ => "many"
    }
```

Patterns are full expressions compared with `==`; `_` is the wildcard. Works
in any expression position, including nested inside other expressions.

### Real runtime overloading

Not a typing hint — actual dispatch at call time, by arity and by type
(builtin types or user classes, respecting MRO):

```python
@overload
def area(r):       return 3.14 * r * r
@overload
def area(w, h):    return w * h

@overload(int)
def kind(x):       return "an int"
@overload(str)
def kind(x):       return "a string"

@overload(Dog)
def speak(a):      return "woof"
@overload(Animal)
def speak(a):      return "generic noise"
```

Typed branches take priority over untyped (arity-only) fallbacks.

### Built-in decorators

No imports, no boilerplate:

```python
@memo                       # automatic memoization
def fib(n): ...

@trace                      # prints call args and return value
def add(a, b): ...

@retry(times=5, on=IOError) # retry on exception
def fetch(): ...
```

### Multi-line lambdas

```python
process = lambda x:
    y = x * 2
    z = y + 1
    return z
```

### Block comments

```python
/* this is a
   multi-line block
   /* and yes, they nest */
   comment */
```

### Elm-style error messages

```
-- SYNTAX ERROR ------------------------------------------------

expected NEWLINE but got ASSIGN ('=')
  --> example.py:7

   5 | def greet(name):
   6 |     if name = "ada":
     |              ^
   7 |         print("hi ada")

help: `=` is assignment, not comparison. Use `==` to compare values.
```

The runtime also suggests close matches for typos:

```
NameError: name 'lenght' is not defined. did you mean 'length'?
```

### The mutable-default fix

Python's most famous footgun:

```python
def append_to(item, lst=[]):
    lst.append(item)
    return lst
```

In CPython, `lst` is shared across calls. **In Mamba it isn't.** Defaults are
re-evaluated per call, the way every Python newcomer expected on day one.

## Examples

Real, runnable Mamba programs live in [`examples/`](examples/):

- [`hello.py`](examples/hello.py) — the smallest possible Mamba program
- [`showcase.py`](examples/showcase.py) — a tour of every Mamba feature

## Project structure

```
src/
  lexer.py         # tokenizer
  parser.py        # recursive-descent parser → AST
  ast_nodes.py     # AST node definitions
  interpreter.py   # tree-walking evaluator + builtins
  errors.py        # Elm/Rust-style error formatter
main.py            # CLI entry point + REPL
tests/             # 183 unittest cases across phases A–G
examples/          # runnable .py demos
assets/            # logo and visual identity
```

## Running the tests

```bash
python3 -m unittest discover -s tests -q
```

## Roadmap

Mamba evolves in **phases**. Each phase ships behind a green test suite.

| Phase | Title                                                       | Status  |
|-------|-------------------------------------------------------------|---------|
| A     | Lexer, parser, base interpreter                             | done    |
| B     | Classes, MRO (C3), `super`, metaclass                       | done    |
| C     | Built-ins, ternary, chained compares                        | done    |
| D     | Elm-style errors + did-you-mean                             | done    |
| E     | Block comments, multi-line lambdas, mutable-default fix     | done    |
| F     | `\|>`, `??`, `?.`/`?[`, `match`, `@memo`/`@trace`/`@retry`  | done    |
| G     | Real runtime function overloading                           | done    |
| H     | Load-bearing typing (hints feed runtime/perf)               | planned |
| I     | GIL-free parallel execution                                 | planned |
| J     | Built-in package manager                                    | planned |

Longer-term ideas: parse-time macros, structured concurrency in the core,
native hot reload, a real REPL with multiline editing and visual inspection.

## Status

Mamba is **experimental**. The language is real and the test suite is real,
but the implementation is a tree-walking interpreter and is not yet tuned for
performance. Use it to play, to learn how a language is built, and to try
syntax that CPython has been refusing for years.

## License

MIT.
