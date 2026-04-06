"""AST node definitions for Mamba.

Each node is a small dataclass-like object. Kept hand-written (no @dataclass)
so the structure is explicit and easy to extend.
"""


class Node:
    pass


# ---------- expressions ----------

class Num(Node):
    def __init__(self, value): self.value = value
    def __repr__(self): return f"Num({self.value!r})"


class Str(Node):
    def __init__(self, value): self.value = value
    def __repr__(self): return f"Str({self.value!r})"


class Bool(Node):
    def __init__(self, value): self.value = value
    def __repr__(self): return f"Bool({self.value!r})"


class NoneLit(Node):
    def __repr__(self): return "None"


class Name(Node):
    def __init__(self, name): self.name = name
    def __repr__(self): return f"Name({self.name!r})"


class BinOp(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right
    def __repr__(self): return f"BinOp({self.op!r}, {self.left}, {self.right})"


class UnaryOp(Node):
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand
    def __repr__(self): return f"UnaryOp({self.op!r}, {self.operand})"


class BoolOp(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right
    def __repr__(self): return f"BoolOp({self.op!r}, {self.left}, {self.right})"


class Compare(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right
    def __repr__(self): return f"Compare({self.op!r}, {self.left}, {self.right})"


class Call(Node):
    def __init__(self, func, args, kwargs=None):
        self.func = func
        self.args = args         # list[expr]
        self.kwargs = kwargs or []  # list[(name, expr)]
    def __repr__(self): return f"Call({self.func}, {self.args}, {self.kwargs})"


class FString(Node):
    def __init__(self, segments):
        # list of ('text', str) or ('expr', ast_node)
        self.segments = segments
    def __repr__(self): return f"FString({self.segments})"


class Slice(Node):
    def __init__(self, start, stop, step):
        self.start = start
        self.stop = stop
        self.step = step
    def __repr__(self): return f"Slice({self.start}, {self.stop}, {self.step})"


class Attribute(Node):
    def __init__(self, obj, attr):
        self.obj = obj
        self.attr = attr
    def __repr__(self): return f"Attribute({self.obj}, {self.attr!r})"


class Subscript(Node):
    def __init__(self, obj, index):
        self.obj = obj
        self.index = index
    def __repr__(self): return f"Subscript({self.obj}, {self.index})"


class ListLit(Node):
    def __init__(self, elts): self.elts = elts
    def __repr__(self): return f"ListLit({self.elts})"


class DictLit(Node):
    def __init__(self, pairs): self.pairs = pairs  # list[(key, value)]
    def __repr__(self): return f"DictLit({self.pairs})"


class TupleLit(Node):
    def __init__(self, elts): self.elts = elts
    def __repr__(self): return f"TupleLit({self.elts})"


class SetLit(Node):
    def __init__(self, elts): self.elts = elts
    def __repr__(self): return f"SetLit({self.elts})"


class CompFor(Node):
    """One `for target in iter (if cond)*` clause inside a comprehension."""
    def __init__(self, target, iter, ifs):
        self.target = target
        self.iter = iter
        self.ifs = ifs  # list[expr]


class ListComp(Node):
    def __init__(self, element, generators):
        self.element = element
        self.generators = generators  # list[CompFor]
    def __repr__(self): return f"ListComp({self.element}, {self.generators})"


class SetComp(Node):
    def __init__(self, element, generators):
        self.element = element
        self.generators = generators
    def __repr__(self): return f"SetComp({self.element}, {self.generators})"


class DictComp(Node):
    def __init__(self, key, value, generators):
        self.key = key
        self.value = value
        self.generators = generators
    def __repr__(self): return f"DictComp({self.key}, {self.value}, {self.generators})"


# ---------- statements ----------

class ExprStmt(Node):
    def __init__(self, expr): self.expr = expr
    def __repr__(self): return f"ExprStmt({self.expr})"


class Assign(Node):
    def __init__(self, target, value):
        self.target = target  # Name node
        self.value = value
    def __repr__(self): return f"Assign({self.target}, {self.value})"


class If(Node):
    def __init__(self, test, body, orelse):
        self.test = test
        self.body = body          # list[Node]
        self.orelse = orelse      # list[Node]
    def __repr__(self): return f"If({self.test}, body={self.body}, orelse={self.orelse})"


class While(Node):
    def __init__(self, test, body):
        self.test = test
        self.body = body
    def __repr__(self): return f"While({self.test}, {self.body})"


class FunctionDef(Node):
    def __init__(self, name, params, defaults, vararg, kwarg, body):
        self.name = name
        self.params = params      # list[str]
        self.defaults = defaults  # list[expr|None] aligned with params
        self.vararg = vararg      # str or None
        self.kwarg = kwarg        # str or None
        self.body = body
    def __repr__(self): return f"FunctionDef({self.name}, {self.params})"


class AugAssign(Node):
    def __init__(self, target, op, value):
        self.target = target
        self.op = op  # '+', '-', '*', '/', '%'
        self.value = value
    def __repr__(self): return f"AugAssign({self.target}, {self.op}=, {self.value})"


class Return(Node):
    def __init__(self, value): self.value = value
    def __repr__(self): return f"Return({self.value})"


class Pass(Node):
    def __repr__(self): return "Pass"


class Break(Node):
    def __repr__(self): return "Break"


class Continue(Node):
    def __repr__(self): return "Continue"


class For(Node):
    def __init__(self, target, iter, body):
        self.target = target  # Name
        self.iter = iter
        self.body = body
    def __repr__(self): return f"For({self.target}, {self.iter}, {self.body})"


class ClassDef(Node):
    def __init__(self, name, bases, body):
        self.name = name
        self.bases = bases    # list[expr]
        self.body = body      # list[stmt]
    def __repr__(self): return f"ClassDef({self.name}, {self.bases}, {self.body})"


class Try(Node):
    def __init__(self, body, handlers, finallybody):
        self.body = body
        self.handlers = handlers      # list[ExceptHandler]
        self.finallybody = finallybody  # list[stmt]
    def __repr__(self): return f"Try({self.body}, {self.handlers}, {self.finallybody})"


class ExceptHandler(Node):
    def __init__(self, exc_type, name, body):
        self.exc_type = exc_type  # expr or None (bare except)
        self.name = name          # str or None
        self.body = body
    def __repr__(self): return f"ExceptHandler({self.exc_type}, {self.name}, {self.body})"


class Raise(Node):
    def __init__(self, exc): self.exc = exc
    def __repr__(self): return f"Raise({self.exc})"


class Import(Node):
    def __init__(self, name, alias):
        self.name = name
        self.alias = alias
    def __repr__(self): return f"Import({self.name}, {self.alias})"


class FromImport(Node):
    def __init__(self, module, names):
        self.module = module
        self.names = names  # list[(name, alias)]
    def __repr__(self): return f"FromImport({self.module}, {self.names})"


class Module(Node):
    def __init__(self, body): self.body = body
    def __repr__(self): return f"Module({self.body})"
