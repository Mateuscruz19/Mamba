"""Tree-walking interpreter for the Mamba subset."""

import os

from . import ast_nodes as ast
from .errors import MambaRuntimeError


# ---------- environment ----------

class Environment:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def get(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise NameError(f"name {name!r} is not defined")

    def set(self, name, value):
        self.vars[name] = value


# ---------- callable wrappers ----------

class Function:
    def __init__(self, decl, closure):
        self.decl = decl
        self.closure = closure

    def call(self, interp, args, kwargs=None):
        kwargs = dict(kwargs or {})
        decl = self.decl
        env = Environment(parent=self.closure)

        n_params = len(decl.params)
        positional = list(args)

        # Bind positionals to params
        n_pos_to_bind = min(len(positional), n_params)
        for i in range(n_pos_to_bind):
            env.set(decl.params[i], positional[i])
        extra_positional = positional[n_pos_to_bind:]

        # Fill remaining params from kwargs / defaults
        for i in range(n_pos_to_bind, n_params):
            name = decl.params[i]
            if name in kwargs:
                env.set(name, kwargs.pop(name))
            elif decl.defaults[i] is not None:
                env.set(name, interp.eval_expr(decl.defaults[i], self.closure))
            else:
                raise TypeError(
                    f"{decl.name}() missing required argument: {name!r}"
                )

        # Vararg
        if decl.vararg is not None:
            env.set(decl.vararg, tuple(extra_positional))
        elif extra_positional:
            raise TypeError(
                f"{decl.name}() takes {n_params} positional arguments "
                f"but {len(positional)} were given"
            )

        # **kwargs
        if decl.kwarg is not None:
            env.set(decl.kwarg, dict(kwargs))
        elif kwargs:
            raise TypeError(
                f"{decl.name}() got unexpected keyword argument "
                f"{next(iter(kwargs))!r}"
            )

        try:
            interp.exec_block(decl.body, env)
        except ReturnSignal as r:
            return r.value
        return None


class BoundMethod:
    def __init__(self, func, instance):
        self.func = func
        self.instance = instance

    def call(self, interp, args, kwargs=None):
        return self.func.call(interp, [self.instance] + list(args), kwargs)


class MambaClass:
    def __init__(self, name, bases, attrs):
        self.name = name
        self.bases = bases  # list[MambaClass]
        self.attrs = attrs  # dict

    def lookup(self, name):
        if name in self.attrs:
            return self.attrs[name]
        for b in self.bases:
            if isinstance(b, MambaClass):
                v = b.lookup(name)
                if v is not None:
                    return v
        return None

    def is_subclass_of(self, other):
        if self is other:
            return True
        for b in self.bases:
            if isinstance(b, MambaClass) and b.is_subclass_of(other):
                return True
        return False

    def call(self, interp, args, kwargs=None):
        instance = MambaInstance(self)
        init = self.lookup('__init__')
        if isinstance(init, Function):
            init.call(interp, [instance] + list(args), kwargs)
        elif args or kwargs:
            raise TypeError(f"{self.name}() takes no arguments")
        return instance


class MambaInstance:
    def __init__(self, klass):
        self._class = klass
        self._fields = {}

    def get(self, name):
        if name in self._fields:
            return self._fields[name]
        attr = self._class.lookup(name)
        if attr is None:
            raise AttributeError(
                f"'{self._class.name}' object has no attribute {name!r}"
            )
        if isinstance(attr, Function):
            return BoundMethod(attr, self)
        return attr

    def set(self, name, value):
        self._fields[name] = value


class Module:
    def __init__(self, name, env):
        self.name = name
        self.env = env

    def get(self, name):
        if name in self.env.vars:
            return self.env.vars[name]
        raise AttributeError(f"module {self.name!r} has no attribute {name!r}")


# ---------- signals ----------

class ReturnSignal(Exception):
    def __init__(self, value): self.value = value


class BreakSignal(Exception): pass
class ContinueSignal(Exception): pass


class MambaException(Exception):
    """Wraps a Mamba instance raised via `raise`."""
    def __init__(self, instance):
        self.instance = instance
        msg = ""
        if isinstance(instance, MambaInstance):
            try:
                msg = str(instance.get('message'))
            except Exception:
                pass
        super().__init__(msg)


# ---------- builtins ----------

def _builtin_print(*args, **kwargs):
    print(*args, **kwargs)


BUILTINS = {
    'print': _builtin_print,
    'len': len,
    'int': int,
    'str': str,
    'float': float,
    'bool': bool,
    'range': range,
    'abs': abs,
    'min': min,
    'max': max,
    'sum': sum,
    'list': list,
    'dict': dict,
    'tuple': tuple,
    'sorted': sorted,
    'reversed': reversed,
    'enumerate': enumerate,
    'zip': zip,
    'map': map,
    'filter': filter,
    'isinstance': lambda obj, cls: (
        cls.is_subclass_of(obj._class)
        if isinstance(obj, MambaInstance) and isinstance(cls, MambaClass)
        else isinstance(obj, cls)
    ),
}


# ---------- interpreter ----------

class Interpreter:
    def __init__(self, file=None):
        self.globals = Environment()
        for name, val in BUILTINS.items():
            self.globals.set(name, val)
        self.file = file
        self._module_cache = {}

    def run(self, module: ast.Module):
        self.exec_block(module.body, self.globals)

    # ---------- statements ----------

    def exec_block(self, stmts, env):
        for s in stmts:
            self.exec_stmt(s, env)

    def exec_stmt(self, node, env):
        m = getattr(self, f"stmt_{type(node).__name__}", None)
        if m is None:
            raise MambaRuntimeError(f"unsupported statement: {type(node).__name__}")
        return m(node, env)

    def stmt_ExprStmt(self, node, env):
        self.eval_expr(node.expr, env)

    def stmt_Assign(self, node, env):
        value = self.eval_expr(node.value, env)
        self._assign_to(node.target, value, env)

    def _assign_to(self, target, value, env):
        if isinstance(target, ast.Name):
            env.set(target.name, value)
        elif isinstance(target, ast.Attribute):
            obj = self.eval_expr(target.obj, env)
            if isinstance(obj, MambaInstance):
                obj.set(target.attr, value)
            else:
                setattr(obj, target.attr, value)
        elif isinstance(target, ast.Subscript):
            obj = self.eval_expr(target.obj, env)
            idx = self._eval_index(target.index, env)
            obj[idx] = value
        elif isinstance(target, ast.TupleLit):
            values = list(value)
            if len(values) != len(target.elts):
                raise ValueError(
                    f"expected {len(target.elts)} values to unpack, got {len(values)}"
                )
            for sub, v in zip(target.elts, values):
                self._assign_to(sub, v, env)
        else:
            raise MambaRuntimeError(f"invalid assignment target: {type(target).__name__}")

    def stmt_AugAssign(self, node, env):
        current = self.eval_expr(node.target, env)
        rhs = self.eval_expr(node.value, env)
        ops = {'+': lambda a, b: a + b, '-': lambda a, b: a - b,
               '*': lambda a, b: a * b, '/': lambda a, b: a / b,
               '%': lambda a, b: a % b}
        self._assign_to(node.target, ops[node.op](current, rhs), env)

    def _eval_index(self, node, env):
        if isinstance(node, ast.Slice):
            s = self.eval_expr(node.start, env) if node.start is not None else None
            e = self.eval_expr(node.stop, env) if node.stop is not None else None
            st = self.eval_expr(node.step, env) if node.step is not None else None
            return slice(s, e, st)
        return self.eval_expr(node, env)

    def stmt_If(self, node, env):
        if self.truthy(self.eval_expr(node.test, env)):
            self.exec_block(node.body, env)
        else:
            self.exec_block(node.orelse, env)

    def stmt_While(self, node, env):
        while self.truthy(self.eval_expr(node.test, env)):
            try:
                self.exec_block(node.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def stmt_For(self, node, env):
        iterable = self.eval_expr(node.iter, env)
        for item in iterable:
            self._assign_to(node.target, item, env)
            try:
                self.exec_block(node.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def stmt_FunctionDef(self, node, env):
        env.set(node.name, Function(node, env))

    def stmt_Return(self, node, env):
        value = self.eval_expr(node.value, env) if node.value is not None else None
        raise ReturnSignal(value)

    def stmt_Pass(self, node, env): pass
    def stmt_Break(self, node, env): raise BreakSignal()
    def stmt_Continue(self, node, env): raise ContinueSignal()

    def stmt_ClassDef(self, node, env):
        bases = [self.eval_expr(b, env) for b in node.bases]
        body_env = Environment(parent=env)
        self.exec_block(node.body, body_env)
        klass = MambaClass(node.name, bases, dict(body_env.vars))
        env.set(node.name, klass)

    def stmt_Raise(self, node, env):
        value = self.eval_expr(node.exc, env)
        if isinstance(value, MambaClass):
            value = value.call(self, [])
        if isinstance(value, MambaInstance):
            raise MambaException(value)
        if isinstance(value, BaseException):
            raise value
        raise TypeError("exceptions must derive from BaseException")

    def stmt_Try(self, node, env):
        try:
            try:
                self.exec_block(node.body, env)
            except MambaException as me:
                handled = False
                for h in node.handlers:
                    if self._handler_matches(h, me.instance, env):
                        handled = True
                        if h.name is not None:
                            env.set(h.name, me.instance)
                        self.exec_block(h.body, env)
                        break
                if not handled:
                    raise
            except (ReturnSignal, BreakSignal, ContinueSignal):
                raise
            except Exception as pyexc:
                handled = False
                for h in node.handlers:
                    if self._handler_matches(h, pyexc, env):
                        handled = True
                        if h.name is not None:
                            env.set(h.name, pyexc)
                        self.exec_block(h.body, env)
                        break
                if not handled:
                    raise
        finally:
            if node.finallybody:
                self.exec_block(node.finallybody, env)

    def _handler_matches(self, handler, exc, env):
        if handler.exc_type is None:
            return True
        target = self.eval_expr(handler.exc_type, env)
        if isinstance(exc, MambaInstance) and isinstance(target, MambaClass):
            return exc._class.is_subclass_of(target)
        if isinstance(target, type) and isinstance(exc, target):
            return True
        return False

    def stmt_Import(self, node, env):
        mod = self._load_module(node.name)
        env.set(node.alias or node.name, mod)

    def stmt_FromImport(self, node, env):
        mod = self._load_module(node.module)
        for name, alias in node.names:
            env.set(alias or name, mod.get(name))

    def _load_module(self, name):
        if name in self._module_cache:
            return self._module_cache[name]
        # Search next to the current file, then cwd
        candidates = []
        if self.file:
            candidates.append(os.path.join(os.path.dirname(self.file), name + ".py"))
        candidates.append(os.path.join(os.getcwd(), name + ".py"))
        path = next((p for p in candidates if os.path.isfile(p)), None)
        if path is None:
            raise ModuleNotFoundError(f"no module named {name!r}")
        from .lexer import Lexer
        from .parser import Parser
        with open(path, 'r', encoding='utf-8') as f:
            source = f.read()
        sub = Interpreter(file=path)
        tree = Parser(Lexer(source).tokenize(), source=source, file=path).parse()
        sub.run(tree)
        mod = Module(name, sub.globals)
        self._module_cache[name] = mod
        return mod

    # ---------- expressions ----------

    def eval_expr(self, node, env):
        m = getattr(self, f"expr_{type(node).__name__}", None)
        if m is None:
            raise MambaRuntimeError(f"unsupported expression: {type(node).__name__}")
        return m(node, env)

    def expr_Num(self, node, env): return node.value
    def expr_Str(self, node, env): return node.value
    def expr_Bool(self, node, env): return node.value
    def expr_NoneLit(self, node, env): return None

    def expr_Name(self, node, env):
        return env.get(node.name)

    def expr_BinOp(self, node, env):
        l = self.eval_expr(node.left, env)
        r = self.eval_expr(node.right, env)
        if node.op == '+':  return l + r
        if node.op == '-':  return l - r
        if node.op == '*':  return l * r
        if node.op == '/':  return l / r
        if node.op == '//': return l // r
        if node.op == '%':  return l % r
        if node.op == '**': return l ** r
        raise MambaRuntimeError(f"unknown binop {node.op!r}")

    def expr_UnaryOp(self, node, env):
        v = self.eval_expr(node.operand, env)
        if node.op == '-': return -v
        if node.op == '+': return +v
        if node.op == 'not': return not self.truthy(v)
        raise MambaRuntimeError(f"unknown unary op {node.op!r}")

    def expr_BoolOp(self, node, env):
        l = self.eval_expr(node.left, env)
        if node.op == 'and':
            return l if not self.truthy(l) else self.eval_expr(node.right, env)
        if node.op == 'or':
            return l if self.truthy(l) else self.eval_expr(node.right, env)
        raise MambaRuntimeError(f"unknown bool op {node.op!r}")

    def expr_Compare(self, node, env):
        l = self.eval_expr(node.left, env)
        r = self.eval_expr(node.right, env)
        ops = {
            '==': lambda a, b: a == b,
            '!=': lambda a, b: a != b,
            '<':  lambda a, b: a < b,
            '>':  lambda a, b: a > b,
            '<=': lambda a, b: a <= b,
            '>=': lambda a, b: a >= b,
            'is': lambda a, b: a is b,
            'is not': lambda a, b: a is not b,
        }
        return ops[node.op](l, r)

    def expr_Call(self, node, env):
        func = self.eval_expr(node.func, env)
        args = [self.eval_expr(a, env) for a in node.args]
        kwargs = {name: self.eval_expr(v, env) for name, v in node.kwargs}
        if isinstance(func, (Function, BoundMethod, MambaClass)):
            return func.call(self, args, kwargs)
        if callable(func):
            return func(*args, **kwargs)
        raise TypeError(f"{func!r} is not callable")

    def expr_Attribute(self, node, env):
        obj = self.eval_expr(node.obj, env)
        if isinstance(obj, MambaInstance):
            return obj.get(node.attr)
        if isinstance(obj, MambaClass):
            v = obj.lookup(node.attr)
            if v is None:
                raise AttributeError(
                    f"class {obj.name!r} has no attribute {node.attr!r}"
                )
            return v
        if isinstance(obj, Module):
            return obj.get(node.attr)
        return getattr(obj, node.attr)

    def expr_Subscript(self, node, env):
        obj = self.eval_expr(node.obj, env)
        idx = self._eval_index(node.index, env)
        return obj[idx]

    def expr_FString(self, node, env):
        out = []
        for kind, payload in node.segments:
            if kind == 'text':
                out.append(payload)
            else:
                out.append(str(self.eval_expr(payload, env)))
        return ''.join(out)

    def expr_ListLit(self, node, env):
        return [self.eval_expr(e, env) for e in node.elts]

    def expr_TupleLit(self, node, env):
        return tuple(self.eval_expr(e, env) for e in node.elts)

    def expr_DictLit(self, node, env):
        return {self.eval_expr(k, env): self.eval_expr(v, env) for k, v in node.pairs}

    @staticmethod
    def truthy(value):
        return bool(value)
