"""Tree-walking interpreter for the Mamba subset."""

import operator
import os

from . import ast_nodes as ast
from .errors import MambaRuntimeError


_BIN_OPS = {
    '+': operator.add, '-': operator.sub, '*': operator.mul,
    '/': operator.truediv, '//': operator.floordiv, '%': operator.mod,
    '**': operator.pow,
}

_BIN_DUNDERS = {
    '+':  ('__add__',     '__radd__'),
    '-':  ('__sub__',     '__rsub__'),
    '*':  ('__mul__',     '__rmul__'),
    '/':  ('__truediv__', '__rtruediv__'),
    '//': ('__floordiv__', '__rfloordiv__'),
    '%':  ('__mod__',     '__rmod__'),
    '**': ('__pow__',     '__rpow__'),
}

_CMP_OPS = {
    '==': operator.eq, '!=': operator.ne,
    '<':  operator.lt, '>':  operator.gt,
    '<=': operator.le, '>=': operator.ge,
    'is': operator.is_, 'is not': operator.is_not,
    'in':     lambda a, b: a in b,
    'not in': lambda a, b: a not in b,
}

_CMP_DUNDERS = {
    '==': ('__eq__', '__eq__'),
    '!=': ('__ne__', '__ne__'),
    '<':  ('__lt__', '__gt__'),
    '>':  ('__gt__', '__lt__'),
    '<=': ('__le__', '__ge__'),
    '>=': ('__ge__', '__le__'),
}


# ---------- environment ----------

class Environment:
    def __init__(self, parent=None, globals=None):
        self.vars = {}
        self.parent = parent
        # Module globals: each environment carries a reference so 'global'
        # writes can find their target. Module-level envs point to themselves.
        self.globals = globals if globals is not None else self
        self.global_names = set()
        self.nonlocal_names = set()

    def get(self, name):
        if name in self.global_names:
            if name in self.globals.vars:
                return self.globals.vars[name]
            raise NameError(self._not_defined_msg(name))
        if name in self.vars:
            return self.vars[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise NameError(self._not_defined_msg(name))

    def all_visible_names(self):
        names = set(self.vars.keys())
        if self.parent is not None:
            names.update(self.parent.all_visible_names())
        else:
            names.update(self.globals.vars.keys())
        return names

    def _not_defined_msg(self, name):
        from .errors import suggest
        candidates = self.all_visible_names()
        s = suggest(name, candidates)
        msg = f"name {name!r} is not defined"
        if s:
            msg += f". did you mean {s!r}?"
        return msg

    def set(self, name, value):
        if name in self.global_names:
            self.globals.vars[name] = value
            return
        if name in self.nonlocal_names:
            env = self.parent
            while env is not None and env is not self.globals:
                if name in env.vars:
                    env.vars[name] = value
                    return
                env = env.parent
            raise SyntaxError(f"no binding for nonlocal {name!r}")
        self.vars[name] = value


# ---------- callable wrappers ----------

def _body_has_yield(stmts):
    """Walk statements looking for a Yield, but don't descend into nested
    function/class/lambda definitions."""
    for s in stmts:
        if _node_has_yield(s):
            return True
    return False


def _node_has_yield(node):
    if isinstance(node, ast.Yield):
        return True
    if isinstance(node, (ast.FunctionDef, ast.Lambda, ast.ClassDef)):
        return False
    if not isinstance(node, ast.Node):
        return False
    for attr in vars(node).values():
        if isinstance(attr, list):
            for x in attr:
                if isinstance(x, ast.Node) and _node_has_yield(x):
                    return True
                if isinstance(x, tuple):
                    for y in x:
                        if isinstance(y, ast.Node) and _node_has_yield(y):
                            return True
        elif isinstance(attr, ast.Node) and _node_has_yield(attr):
            return True
    return False


class Function:
    def __init__(self, decl, closure, interp=None):
        self.decl = decl
        self.closure = closure
        self.interp = interp  # set so Python callers (map/filter/sorted) work
        self.is_generator = _body_has_yield(decl.body)

    def __call__(self, *args, **kwargs):
        return self.call(self.interp, list(args), kwargs)

    def call(self, interp, args, kwargs=None):
        kwargs = dict(kwargs or {})
        decl = self.decl
        env = Environment(parent=self.closure, globals=self.closure.globals)

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

        if self.is_generator:
            def _gen():
                try:
                    yield from interp.gen_exec_block(decl.body, env)
                except ReturnSignal:
                    return
            return _gen()

        try:
            interp.exec_block(decl.body, env)
        except ReturnSignal as r:
            return r.value
        return None


class BoundMethod:
    def __init__(self, func, instance, defining_class=None):
        self.func = func
        self.instance = instance
        self.defining_class = defining_class

    def _push(self, interp):
        if interp is not None and self.defining_class is not None:
            interp.method_stack.append((self.defining_class, self.instance))
            return True
        return False

    def _pop(self, interp, pushed):
        if pushed:
            interp.method_stack.pop()

    def __call__(self, *args, **kwargs):
        interp = self.func.interp
        pushed = self._push(interp)
        try:
            return self.func.call(interp, [self.instance] + list(args), kwargs)
        finally:
            self._pop(interp, pushed)

    def call(self, interp, args, kwargs=None):
        pushed = self._push(interp)
        try:
            return self.func.call(interp, [self.instance] + list(args), kwargs)
        finally:
            self._pop(interp, pushed)


class SuperProxy:
    def __init__(self, start_class, instance):
        self.start_class = start_class
        self.instance = instance

    def get(self, name):
        inst = self.instance
        klass = inst._class if isinstance(inst, MambaInstance) else inst
        defining, attr = klass.lookup_from(name, self.start_class)
        if attr is None:
            raise AttributeError(f"'super' object has no attribute {name!r}")
        if isinstance(attr, Function):
            return BoundMethod(attr, inst, defining_class=defining)
        if isinstance(attr, StaticMethod):
            return attr.func
        if isinstance(attr, ClassMethod):
            inner = attr.func
            target = inst if isinstance(inst, MambaClass) else inst._class
            if isinstance(inner, Function):
                return BoundMethod(inner, target, defining_class=defining)
            return lambda *a, **kw: inner(target, *a, **kw)
        return attr


def _c3_merge(seqs):
    result = []
    seqs = [list(s) for s in seqs if s]
    while seqs:
        head = None
        for s in seqs:
            cand = s[0]
            if not any(cand in rest[1:] for rest in seqs):
                head = cand
                break
        if head is None:
            raise TypeError("Cannot create a consistent MRO")
        result.append(head)
        seqs = [
            (s[1:] if s and s[0] is head else s)
            for s in seqs
        ]
        seqs = [s for s in seqs if s]
    return result


def _compute_mro(cls):
    mro_bases = [
        _compute_mro(b) for b in cls.bases if isinstance(b, MambaClass)
    ]
    return [cls] + _c3_merge(mro_bases + [list(cls.bases)])


class MambaClass:
    def __init__(self, name, bases, attrs):
        self.name = name
        self.bases = [b for b in bases if isinstance(b, MambaClass)]
        self.attrs = attrs  # dict
        self.mro = _compute_mro(self)

    def lookup(self, name):
        for c in self.mro:
            if isinstance(c, MambaClass) and name in c.attrs:
                return c.attrs[name]
        return None

    def lookup_from(self, name, start_after):
        """Lookup `name` in MRO, starting after `start_after` class."""
        found = False
        for c in self.mro:
            if not found:
                if c is start_after:
                    found = True
                continue
            if isinstance(c, MambaClass) and name in c.attrs:
                return c, c.attrs[name]
        return None, None

    def is_subclass_of(self, other):
        return other in self.mro

    def call(self, interp, args, kwargs=None):
        instance = MambaInstance(self)
        defining = None
        for c in self.mro:
            if isinstance(c, MambaClass) and '__init__' in c.attrs:
                defining = c
                init = c.attrs['__init__']
                break
        else:
            init = None
        if isinstance(init, Function):
            BoundMethod(init, instance, defining_class=defining).call(
                interp, list(args), kwargs
            )
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
        defining = None
        for c in self._class.mro:
            if isinstance(c, MambaClass) and name in c.attrs:
                defining = c
                attr = c.attrs[name]
                break
        else:
            attr = None
        if attr is None:
            from .errors import suggest
            cands = set(self._fields.keys())
            for c in self._class.mro:
                if isinstance(c, MambaClass):
                    cands.update(c.attrs.keys())
            s = suggest(name, cands)
            msg = f"'{self._class.name}' object has no attribute {name!r}"
            if s:
                msg += f". did you mean {s!r}?"
            raise AttributeError(msg)
        if isinstance(attr, Function):
            return BoundMethod(attr, self, defining_class=defining)
        if isinstance(attr, StaticMethod):
            return attr.func
        if isinstance(attr, ClassMethod):
            inner = attr.func
            if isinstance(inner, Function):
                return BoundMethod(inner, self._class, defining_class=defining)
            return lambda *a, **kw: inner(self._class, *a, **kw)
        if isinstance(attr, Property):
            fget = attr.fget
            if isinstance(fget, Function):
                return fget.call(fget.interp, [self], {})
            return fget(self)
        return attr

    def set(self, name, value):
        attr = self._class.lookup(name)
        if isinstance(attr, Property):
            if attr.fset is None:
                raise AttributeError(f"can't set attribute {name!r}")
            fset = attr.fset
            if isinstance(fset, Function):
                fset.call(fset.interp, [self, value], {})
            else:
                fset(self, value)
            return
        self._fields[name] = value

    def _has(self, name):
        return name in self._fields or self._class.lookup(name) is not None

    # Make Mamba instances cooperate with Python protocols by delegating to
    # dunder methods defined on the Mamba class.

    def __iter__(self):
        if not self._has('__iter__'):
            raise TypeError(f"'{self._class.name}' object is not iterable")
        it = self.get('__iter__')()
        return _IterAdapter(it)

    def __len__(self):
        if not self._has('__len__'):
            raise TypeError(f"object of type '{self._class.name}' has no len()")
        return self.get('__len__')()

    def __bool__(self):
        if self._has('__bool__'):
            return bool(self.get('__bool__')())
        if self._has('__len__'):
            return self.get('__len__')() != 0
        return True

    def __getitem__(self, key):
        if not self._has('__getitem__'):
            raise TypeError(f"'{self._class.name}' object is not subscriptable")
        return self.get('__getitem__')(key)

    def __setitem__(self, key, value):
        if not self._has('__setitem__'):
            raise TypeError(
                f"'{self._class.name}' object does not support item assignment"
            )
        self.get('__setitem__')(key, value)

    def __contains__(self, item):
        if self._has('__contains__'):
            return bool(self.get('__contains__')(item))
        # Fall back to iteration
        for x in self:
            if x == item:
                return True
        return False

    def __call__(self, *args, **kwargs):
        if not self._has('__call__'):
            raise TypeError(f"'{self._class.name}' object is not callable")
        method = self.get('__call__')
        return method(*args, **kwargs)

    def __str__(self):
        if self._has('__str__'):
            return str(self.get('__str__')())
        if self._has('__repr__'):
            return str(self.get('__repr__')())
        return f"<{self._class.name} object>"

    def __repr__(self):
        if self._has('__repr__'):
            return str(self.get('__repr__')())
        return f"<{self._class.name} object>"

    def __eq__(self, other):
        if self._has('__eq__'):
            return self.get('__eq__')(other)
        return self is other

    def __ne__(self, other):
        if self._has('__ne__'):
            return self.get('__ne__')(other)
        return not self.__eq__(other)

    def __lt__(self, other):
        if self._has('__lt__'):
            return self.get('__lt__')(other)
        return NotImplemented

    def __le__(self, other):
        if self._has('__le__'):
            return self.get('__le__')(other)
        return NotImplemented

    def __gt__(self, other):
        if self._has('__gt__'):
            return self.get('__gt__')(other)
        return NotImplemented

    def __ge__(self, other):
        if self._has('__ge__'):
            return self.get('__ge__')(other)
        return NotImplemented

    def __hash__(self):
        if self._has('__hash__'):
            return self.get('__hash__')()
        return id(self)


class _IterAdapter:
    """Wraps a Mamba iterator object so Python's `for` can iterate over it."""
    def __init__(self, mamba_iter):
        self.it = mamba_iter

    def __iter__(self):
        return self

    def __next__(self):
        try:
            if isinstance(self.it, MambaInstance):
                return self.it.get('__next__')()
            return next(self.it)
        except MambaException as me:
            inst = me.instance
            if (isinstance(inst, MambaInstance)
                    and inst._class.name == 'StopIteration'):
                raise StopIteration
            raise


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


def _mamba_getattr(obj, name, *default):
    try:
        if isinstance(obj, MambaInstance):
            return obj.get(name)
        if isinstance(obj, MambaClass):
            v = obj.lookup(name)
            if v is None:
                raise AttributeError(name)
            return v
        return getattr(obj, name)
    except AttributeError:
        if default:
            return default[0]
        raise


class StaticMethod:
    def __init__(self, func): self.func = func


class ClassMethod:
    def __init__(self, func): self.func = func


class Property:
    def __init__(self, fget, fset=None):
        self.fget = fget
        self.fset = fset

    def setter(self, fn):
        return Property(self.fget, fn)


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
    'iter': iter,
    'next': next,
    'hash': hash,
    'id': id,
    'type': type,
    'repr': repr,
    'zip': zip,
    'map': map,
    'filter': filter,
    'isinstance': lambda obj, cls: (
        cls.is_subclass_of(obj._class)
        if isinstance(obj, MambaInstance) and isinstance(cls, MambaClass)
        else isinstance(obj, cls)
    ),
    'all': all,
    'any': any,
    'round': round,
    'chr': chr,
    'ord': ord,
    'hex': hex,
    'bin': bin,
    'oct': oct,
    'divmod': divmod,
    'pow': pow,
    'set': set,
    'frozenset': frozenset,
    'bytes': bytes,
    'bytearray': bytearray,
    'complex': complex,
    'input': input,
    'open': open,
    'format': format,
    'callable': lambda x: (
        isinstance(x, (Function, BoundMethod, MambaClass)) or callable(x)
    ),
    'getattr': lambda *args: _mamba_getattr(*args),
    'setattr': lambda obj, name, value: (
        obj.set(name, value) if isinstance(obj, MambaInstance)
        else setattr(obj, name, value)
    ),
    'hasattr': lambda obj, name: (
        (name in obj._fields or obj._class.lookup(name) is not None)
        if isinstance(obj, MambaInstance)
        else (obj.lookup(name) is not None)
        if isinstance(obj, MambaClass)
        else hasattr(obj, name)
    ),
    'delattr': delattr,
    'vars': vars,
    'dir': dir,
    'slice': slice,
    'object': object,
    # Built-in exception hierarchy (delegated to Python's own classes)
    'Exception': Exception,
    'BaseException': BaseException,
    'ValueError': ValueError,
    'TypeError': TypeError,
    'KeyError': KeyError,
    'IndexError': IndexError,
    'AttributeError': AttributeError,
    'NameError': NameError,
    'ZeroDivisionError': ZeroDivisionError,
    'StopIteration': StopIteration,
    'RuntimeError': RuntimeError,
    'NotImplementedError': NotImplementedError,
    'FileNotFoundError': FileNotFoundError,
    'OSError': OSError,
    'ArithmeticError': ArithmeticError,
    'LookupError': LookupError,
    'AssertionError': AssertionError,
    'staticmethod': StaticMethod,
    'classmethod': ClassMethod,
    'property': Property,
}


# ---------- interpreter ----------

def _make_super(interp):
    def _super(*args):
        if len(args) == 0:
            if not interp.method_stack:
                raise RuntimeError("super(): no current method")
            cls, inst = interp.method_stack[-1]
            return SuperProxy(cls, inst)
        if len(args) == 2:
            return SuperProxy(args[0], args[1])
        raise TypeError("super() takes 0 or 2 arguments")
    return _super


class Interpreter:
    def __init__(self, file=None):
        self.globals = Environment()
        for name, val in BUILTINS.items():
            self.globals.set(name, val)
        self.file = file
        self._module_cache = {}
        self.method_stack = []  # list[(defining_class, instance)]
        self.globals.set('super', _make_super(self))

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
        value = Function(node, env, interp=self)
        for dec in reversed(node.decorators):
            value = self.call_value(self.eval_expr(dec, env), [value], {})
        env.set(node.name, value)

    def call_value(self, fn, args, kwargs):
        if isinstance(fn, (Function, BoundMethod)):
            return fn.call(self, args, kwargs)
        if isinstance(fn, MambaClass):
            return fn.call(self, args, kwargs)
        return fn(*args, **kwargs)

    def stmt_Return(self, node, env):
        value = self.eval_expr(node.value, env) if node.value is not None else None
        raise ReturnSignal(value)

    def stmt_Assert(self, node, env):
        if not self.truthy(self.eval_expr(node.test, env)):
            msg = self.eval_expr(node.msg, env) if node.msg is not None else None
            raise AssertionError(msg) if msg is not None else AssertionError()

    def stmt_Delete(self, node, env):
        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.name in env.vars:
                    del env.vars[target.name]
                else:
                    raise NameError(f"name {target.name!r} is not defined")
            elif isinstance(target, ast.Attribute):
                obj = self.eval_expr(target.obj, env)
                if isinstance(obj, MambaInstance):
                    if target.attr in obj._fields:
                        del obj._fields[target.attr]
                    else:
                        raise AttributeError(target.attr)
                else:
                    delattr(obj, target.attr)
            elif isinstance(target, ast.Subscript):
                obj = self.eval_expr(target.obj, env)
                idx = self._eval_index(target.index, env)
                del obj[idx]
            else:
                raise TypeError(f"can't delete {type(target).__name__}")

    def stmt_Pass(self, node, env): pass
    def stmt_Break(self, node, env): raise BreakSignal()
    def stmt_Continue(self, node, env): raise ContinueSignal()

    def stmt_Global(self, node, env):
        for name in node.names:
            env.global_names.add(name)

    def stmt_Nonlocal(self, node, env):
        for name in node.names:
            env.nonlocal_names.add(name)

    def stmt_ClassDef(self, node, env):
        bases = [self.eval_expr(b, env) for b in node.bases]
        body_env = Environment(parent=env, globals=env.globals)
        self.exec_block(node.body, body_env)
        attrs = dict(body_env.vars)
        if node.metaclass is not None:
            meta = self.eval_expr(node.metaclass, env)
            klass = self.call_value(meta, [node.name, bases, attrs], {})
        else:
            klass = MambaClass(node.name, bases, attrs)
        value = klass
        for dec in reversed(node.decorators):
            value = self.call_value(self.eval_expr(dec, env), [value], {})
        env.set(node.name, value)

    def stmt_Raise(self, node, env):
        value = self.eval_expr(node.exc, env)
        if isinstance(value, MambaClass):
            value = value.call(self, [])
        if isinstance(value, type) and issubclass(value, BaseException):
            value = value()
        if isinstance(value, MambaInstance):
            raise MambaException(value)
        if isinstance(value, BaseException):
            raise value
        raise TypeError("exceptions must derive from BaseException")

    def stmt_With(self, node, env):
        ctx = self.eval_expr(node.context, env)
        # Resolve __enter__ / __exit__ supporting both Mamba and Python objects
        enter = self._lookup_dunder(ctx, '__enter__')
        exit_ = self._lookup_dunder(ctx, '__exit__')
        value = enter() if not callable(enter) else enter()
        if node.var is not None:
            env.set(node.var, value)
        try:
            self.exec_block(node.body, env)
        except BaseException as e:
            if not exit_(type(e), e, None):
                raise
        else:
            exit_(None, None, None)

    def _lookup_dunder(self, obj, name):
        if isinstance(obj, MambaInstance):
            return obj.get(name)
        return getattr(obj, name)

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
        return self._exc_matches(exc, target)

    def _exc_matches(self, exc, target):
        if isinstance(target, tuple):
            return any(self._exc_matches(exc, t) for t in target)
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

    # ---------- generator-aware execution ----------

    def gen_exec_block(self, stmts, env):
        for s in stmts:
            yield from self.gen_exec_stmt(s, env)

    def gen_exec_stmt(self, node, env):
        # yield as a statement
        if isinstance(node, ast.ExprStmt) and isinstance(node.expr, ast.Yield):
            v = self.eval_expr(node.expr.value, env) if node.expr.value is not None else None
            yield v
            return
        # control flow that may contain yields
        if isinstance(node, ast.If):
            target = node.body if self.truthy(self.eval_expr(node.test, env)) else node.orelse
            yield from self.gen_exec_block(target, env)
            return
        if isinstance(node, ast.While):
            while self.truthy(self.eval_expr(node.test, env)):
                try:
                    yield from self.gen_exec_block(node.body, env)
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
            return
        if isinstance(node, ast.For):
            iterable = self.eval_expr(node.iter, env)
            for item in iterable:
                self._assign_to(node.target, item, env)
                try:
                    yield from self.gen_exec_block(node.body, env)
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
            return
        if isinstance(node, ast.Try):
            # Defer to plain exec — yields inside try blocks are not supported.
            self.exec_stmt(node, env)
            return
        # leaf / non-yielding stmt: just execute it
        self.exec_stmt(node, env)

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
        op = node.op
        # Mamba instance dunders take precedence so user classes can
        # override arithmetic. Try left operand first, then reflected on right.
        dunder, rdunder = _BIN_DUNDERS[op]
        if isinstance(l, MambaInstance) and l._has(dunder):
            return l.get(dunder)(r)
        if isinstance(r, MambaInstance) and r._has(rdunder):
            return r.get(rdunder)(l)
        return _BIN_OPS[op](l, r)

    def expr_UnaryOp(self, node, env):
        v = self.eval_expr(node.operand, env)
        if node.op == 'not': return not self.truthy(v)
        if isinstance(v, MambaInstance):
            dunder = {'-': '__neg__', '+': '__pos__'}.get(node.op)
            if dunder and v._has(dunder):
                return v.get(dunder)()
        if node.op == '-': return -v
        if node.op == '+': return +v
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
        op = node.op
        if op in _CMP_DUNDERS:
            dunder, rdunder = _CMP_DUNDERS[op]
            if isinstance(l, MambaInstance) and l._has(dunder):
                return l.get(dunder)(r)
            if isinstance(r, MambaInstance) and r._has(rdunder):
                return r.get(rdunder)(l)
        return _CMP_OPS[op](l, r)

    def expr_Call(self, node, env):
        func = self.eval_expr(node.func, env)
        if getattr(node, 'optional', False) and func is None:
            return None
        args = []
        for a in node.args:
            if isinstance(a, ast.Starred):
                args.extend(self.eval_expr(a.value, env))
            else:
                args.append(self.eval_expr(a, env))
        kwargs = {}
        for name, v in node.kwargs:
            if name is None:
                kwargs.update(self.eval_expr(v, env))
            else:
                kwargs[name] = self.eval_expr(v, env)
        if isinstance(func, (Function, BoundMethod, MambaClass)):
            return func.call(self, args, kwargs)
        if callable(func):
            return func(*args, **kwargs)
        raise TypeError(f"{func!r} is not callable")

    def expr_Attribute(self, node, env):
        obj = self.eval_expr(node.obj, env)
        if getattr(node, 'optional', False):
            if obj is None:
                return None
            try:
                return self._do_attr(obj, node.attr)
            except AttributeError:
                return None
        return self._do_attr(obj, node.attr)

    def _do_attr(self, obj, attr):
        if isinstance(obj, SuperProxy):
            return obj.get(attr)
        if isinstance(obj, MambaInstance):
            return obj.get(attr)
        if isinstance(obj, MambaClass):
            defining = None
            for c in obj.mro:
                if isinstance(c, MambaClass) and attr in c.attrs:
                    defining = c
                    v = c.attrs[attr]
                    break
            else:
                v = None
            if v is None:
                from .errors import suggest
                cands = set()
                for c in obj.mro:
                    if isinstance(c, MambaClass):
                        cands.update(c.attrs.keys())
                s = suggest(attr, cands)
                msg = f"class {obj.name!r} has no attribute {attr!r}"
                if s:
                    msg += f". did you mean {s!r}?"
                raise AttributeError(msg)
            if isinstance(v, StaticMethod):
                return v.func
            if isinstance(v, ClassMethod):
                inner = v.func
                if isinstance(inner, Function):
                    return BoundMethod(inner, obj, defining_class=defining)
                return lambda *a, **kw: inner(obj, *a, **kw)
            return v
        if isinstance(obj, Module):
            return obj.get(attr)
        try:
            return getattr(obj, attr)
        except AttributeError:
            from .errors import suggest
            cands = [n for n in dir(obj) if not n.startswith('_')]
            s = suggest(attr, cands)
            msg = (f"{type(obj).__name__!r} object has no attribute "
                   f"{attr!r}")
            if s:
                msg += f". did you mean {s!r}?"
            raise AttributeError(msg)

    def expr_Subscript(self, node, env):
        obj = self.eval_expr(node.obj, env)
        if getattr(node, 'optional', False):
            if obj is None:
                return None
            idx = self._eval_index(node.index, env)
            try:
                return obj[idx]
            except (KeyError, IndexError):
                return None
        idx = self._eval_index(node.index, env)
        return obj[idx]

    def expr_IfExpr(self, node, env):
        if self.truthy(self.eval_expr(node.test, env)):
            return self.eval_expr(node.body, env)
        return self.eval_expr(node.orelse, env)

    def expr_MatchExpr(self, node, env):
        subject = self.eval_expr(node.subject, env)
        for pat, result in node.cases:
            if pat is None:  # wildcard `_`
                return self.eval_expr(result, env)
            if self.eval_expr(pat, env) == subject:
                return self.eval_expr(result, env)
        raise ValueError(f"no match arm matched {subject!r}")

    def expr_NoneCoalesce(self, node, env):
        left = self.eval_expr(node.left, env)
        if left is not None:
            return left
        return self.eval_expr(node.right, env)

    def expr_Lambda(self, node, env):
        # body is either a single expression (classic lambda) or a list
        # of statements (Mamba multi-line lambda extension).
        if isinstance(node.body, list):
            body_stmts = node.body
        else:
            body_stmts = [ast.Return(node.body)]
        decl = ast.FunctionDef(
            name='<lambda>',
            params=list(node.params),
            defaults=list(node.defaults),
            vararg=None,
            kwarg=None,
            body=body_stmts,
        )
        return Function(decl, env, interp=self)

    def expr_FString(self, node, env):
        out = []
        for kind, payload in node.segments:
            if kind == 'text':
                out.append(payload)
            else:
                out.append(str(self.eval_expr(payload, env)))
        return ''.join(out)

    def _expand_elts(self, elts, env):
        out = []
        for e in elts:
            if isinstance(e, ast.Starred):
                out.extend(self.eval_expr(e.value, env))
            else:
                out.append(self.eval_expr(e, env))
        return out

    def expr_ListLit(self, node, env):
        return self._expand_elts(node.elts, env)

    def expr_TupleLit(self, node, env):
        return tuple(self._expand_elts(node.elts, env))

    def expr_DictLit(self, node, env):
        out = {}
        for k, v in node.pairs:
            if k is None:
                out.update(self.eval_expr(v, env))
            else:
                out[self.eval_expr(k, env)] = self.eval_expr(v, env)
        return out

    def expr_SetLit(self, node, env):
        return set(self._expand_elts(node.elts, env))

    def expr_ListComp(self, node, env):
        out = []
        self._run_comp(node.generators, 0, env,
                       lambda e: out.append(self.eval_expr(node.element, e)))
        return out

    def expr_SetComp(self, node, env):
        out = set()
        self._run_comp(node.generators, 0, env,
                       lambda e: out.add(self.eval_expr(node.element, e)))
        return out

    def expr_DictComp(self, node, env):
        out = {}
        def emit(e):
            out[self.eval_expr(node.key, e)] = self.eval_expr(node.value, e)
        self._run_comp(node.generators, 0, env, emit)
        return out

    def _run_comp(self, generators, i, env, emit):
        if i == len(generators):
            emit(env)
            return
        gen = generators[i]
        iterable = self.eval_expr(gen.iter, env)
        for item in iterable:
            inner = Environment(parent=env, globals=env.globals)
            self._assign_to(gen.target, item, inner)
            if all(self.truthy(self.eval_expr(c, inner)) for c in gen.ifs):
                self._run_comp(generators, i + 1, inner, emit)

    @staticmethod
    def truthy(value):
        # MambaInstance.__bool__ already delegates to Mamba __bool__/__len__,
        # so plain bool() does the right thing.
        return bool(value)
