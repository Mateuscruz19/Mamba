/* ============================================================
   Mamba Showcase — features that Python (CPython) doesn't have
   Run with:  python3 main.py examples/showcase.py
   ============================================================ */

print("=== 1. Block comments (/* ... */) — even nested ===")
/* outer
   /* inner */
   still outer */
print("block comments above were skipped\n")


print("=== 2. Pipe operator |> ===")

def double(x):
    return x * 2

# Simple pipe
print(5 |> double)                                    # 10

# Chained pipeline (reads top-to-bottom, like a shell)
print([1,2,3,4,5] |> map(lambda x: x*x) |> list)       # [1,4,9,16,25]

# Stdlib idiom: filter(pred, iter) — pipe appends by default
print([1,-2,3,-4,5] |> filter(lambda x: x > 0) |> list) # [1,3,5]

# Method references work too
print("  hello mamba  " |> str.strip |> str.upper)     # HELLO MAMBA

# Explicit position with `_` placeholder
def sub(a, b):
    return a - b
print(10 |> sub(_, 3))                                 # 7  (10 - 3)
print(10 |> sub(3, _))                                 # -7 (3 - 10)
print()


print("=== 3. Multi-line lambdas ===")

classify = lambda n:
    if n > 0:
        return "positive"
    if n < 0:
        return "negative"
    return "zero"

print(classify(5))    # positive
print(classify(-2))   # negative
print(classify(0))    # zero
print()


print("=== 4. Mutable default args fixed (vs Python footgun) ===")

def append_one(x=[]):
    x.append(1)
    return x

# CPython would print [1], [1,1], [1,1,1] — the famous bug.
# Mamba re-evaluates defaults every call.
print(append_one())   # [1]
print(append_one())   # [1]
print(append_one())   # [1]
print()


print("=== 5. Ternary, chained comparisons, star unpacking ===")
x = 7
print("big" if x > 5 else "small")     # big
print(0 < x < 10)                      # True

a = [1, 2]
b = [3, 4]
print([*a, *b, 5])                     # [1,2,3,4,5]
print({**{"x": 1}, "y": 2})            # {'x': 1, 'y': 2}
print()


print("=== 6. Decorators ===")

def shout(f):
    def w(*args, **kwargs):
        return str(f(*args, **kwargs)).upper() + "!!!"
    return w

@shout
def greet(name):
    return f"hello {name}"

print(greet("mamba"))                  # HELLO MAMBA!!!
print()


print("=== 7. Diamond inheritance + super() with C3 MRO ===")

class A:
    def hi(self):
        return "A"
class B(A):
    def hi(self):
        return "B->" + super().hi()
class C(A):
    def hi(self):
        return "C->" + super().hi()
class D(B, C):
    def hi(self):
        return "D->" + super().hi()

print(D().hi())                        # D->B->C->A
print()


print("=== 8. List comprehension with conditional ===")
xs = [x*2 if x > 0 else 0 for x in [-2,-1,0,1,2]]
print(xs)                              # [0,0,0,2,4]
print()


print("=== Done. Try breaking the code below to see Elm-style errors. ===")
# Uncomment one line below to see Mamba's error formatting in action:
#
# countr = 5         # then call: print(counter)   → "did you mean 'countr'?"
# "hi".uppr()        # → "did you mean 'upper'?"
# if x                # → "expected COLON ... help: statements like if/for must end with `:`"
