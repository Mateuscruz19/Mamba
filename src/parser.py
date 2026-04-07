"""Recursive descent parser for the Mamba subset."""

from .lexer import TokenType
from . import ast_nodes as ast
from .errors import MambaSyntaxError


class Parser:
    def __init__(self, tokens, source=None, file=None):
        self.tokens = tokens
        self.pos = 0
        self.source = source
        self.file = file
        self._block_lambda_consumed = False

    # ---------- helpers ----------

    @property
    def cur(self):
        return self.tokens[self.pos]

    def peek(self, offset=0):
        return self.tokens[self.pos + offset]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def check(self, *types):
        return self.cur.type in types

    def match(self, *types):
        if self.check(*types):
            return self.advance()
        return None

    def error(self, msg, hint=None):
        return MambaSyntaxError(
            msg, line=self.cur.line, file=self.file, source=self.source,
            hint=hint,
        )

    def expect(self, type_, msg=None):
        if self.cur.type != type_:
            got = self.cur
            hint = self._hint_for_expect(type_, got)
            raise self.error(
                msg or f"expected {type_.name} but got {got.type.name} "
                       f"({got.value!r})",
                hint=hint,
            )
        return self.advance()

    def _hint_for_expect(self, expected, got):
        # COLON missing after if/while/for/def/class/try/except/else/elif
        if expected == TokenType.COLON:
            return ("statements like `if`, `for`, `while`, `def`, `class` "
                    "must end with a `:` before the indented block.")
        if expected == TokenType.NEWLINE:
            if got.type == TokenType.ASSIGN:
                return ("`=` is assignment, not comparison. "
                        "Use `==` to compare values.")
            return ("each statement must end at a newline. "
                    "did you forget an operator or close a bracket?")
        if expected == TokenType.RPAREN:
            return "unbalanced parentheses — looks like a `)` is missing."
        if expected == TokenType.RBRACK:
            return "unbalanced brackets — looks like a `]` is missing."
        if expected == TokenType.RBRACE:
            return "unbalanced braces — looks like a `}` is missing."
        if expected == TokenType.INDENT:
            return ("expected an indented block. "
                    "indent the body of the previous line with 4 spaces.")
        if expected == TokenType.NAME:
            return ("expected an identifier here "
                    "(a variable, function, or attribute name).")
        return None

    def skip_newlines(self):
        while self.match(TokenType.NEWLINE):
            pass

    # ---------- entry ----------

    def parse(self):
        body = []
        self.skip_newlines()
        while not self.check(TokenType.EOF):
            body.append(self.statement())
            self.skip_newlines()
        return ast.Module(body)

    # ---------- statements ----------

    def statement(self):
        t = self.cur.type
        if t == TokenType.AT:    return self.decorated()
        if t == TokenType.IF:    return self.if_stmt()
        if t == TokenType.WHILE: return self.while_stmt()
        if t == TokenType.FOR:   return self.for_stmt()
        if t == TokenType.DEF:   return self.func_def()
        if t == TokenType.CLASS: return self.class_def()
        if t == TokenType.TRY:   return self.try_stmt()
        if t == TokenType.WITH:  return self.with_stmt()
        return self.simple_stmt()

    def simple_stmt(self):
        t = self.cur.type
        if t == TokenType.RETURN:
            self.advance()
            value = None
            if not self.check(TokenType.NEWLINE, TokenType.EOF):
                value = self.expr()
            self.expect(TokenType.NEWLINE)
            return ast.Return(value)
        if t == TokenType.PASS:
            self.advance(); self.expect(TokenType.NEWLINE); return ast.Pass()
        if t == TokenType.BREAK:
            self.advance(); self.expect(TokenType.NEWLINE); return ast.Break()
        if t == TokenType.CONTINUE:
            self.advance(); self.expect(TokenType.NEWLINE); return ast.Continue()
        if t == TokenType.RAISE:
            self.advance()
            exc = None
            if not self.check(TokenType.NEWLINE, TokenType.EOF):
                exc = self.expr()
            self.expect(TokenType.NEWLINE)
            return ast.Raise(exc)
        if t == TokenType.IMPORT:
            return self.import_stmt()
        if t == TokenType.FROM:
            return self.from_import_stmt()
        if t in (TokenType.GLOBAL, TokenType.NONLOCAL):
            ctor = ast.Global if t == TokenType.GLOBAL else ast.Nonlocal
            self.advance()
            names = [self.expect(TokenType.NAME).value]
            while self.match(TokenType.COMMA):
                names.append(self.expect(TokenType.NAME).value)
            self.expect(TokenType.NEWLINE)
            return ctor(names)
        if t == TokenType.ASSERT:
            self.advance()
            test = self.expr()
            msg = None
            if self.match(TokenType.COMMA):
                msg = self.expr()
            self.expect(TokenType.NEWLINE)
            return ast.Assert(test, msg)
        if t == TokenType.DEL:
            self.advance()
            targets = [self.expr()]
            while self.match(TokenType.COMMA):
                targets.append(self.expr())
            self.expect(TokenType.NEWLINE)
            return ast.Delete(targets)
        if t == TokenType.YIELD:
            self.advance()
            value = None
            if not self.check(TokenType.NEWLINE, TokenType.EOF):
                value = self.expr()
            self.expect(TokenType.NEWLINE)
            return ast.ExprStmt(ast.Yield(value))

        # expression or assignment (possibly with tuple unpacking)
        e = self.expr()
        if self.check(TokenType.COMMA):
            elts = [e]
            while self.match(TokenType.COMMA):
                if self.check(TokenType.ASSIGN, TokenType.NEWLINE):
                    break
                elts.append(self.expr())
            e = ast.TupleLit(elts)

        aug_map = {
            TokenType.PLUS_EQ: '+', TokenType.MINUS_EQ: '-',
            TokenType.STAR_EQ: '*', TokenType.SLASH_EQ: '/',
            TokenType.MOD_EQ: '%',
        }
        if self.cur.type in aug_map:
            op = aug_map[self.advance().type]
            value = self.expr()
            self.expect(TokenType.NEWLINE)
            self._check_lvalue(e)
            return ast.AugAssign(e, op, value)

        if self.match(TokenType.ASSIGN):
            value = self.expr()
            if self.check(TokenType.COMMA):
                relts = [value]
                while self.match(TokenType.COMMA):
                    if self.check(TokenType.NEWLINE):
                        break
                    relts.append(self.expr())
                value = ast.TupleLit(relts)
            self._expect_newline_or_block_end()
            self._check_lvalue(e)
            return ast.Assign(e, value)
        self._expect_newline_or_block_end()
        return ast.ExprStmt(e)

    def _check_lvalue(self, node):
        if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript)):
            return
        if isinstance(node, ast.TupleLit):
            for e in node.elts:
                self._check_lvalue(e)
            return
        raise self.error(f"cannot assign to {type(node).__name__}")

    def import_stmt(self):
        self.expect(TokenType.IMPORT)
        name = self.expect(TokenType.NAME).value
        alias = None
        if self.match(TokenType.AS):
            alias = self.expect(TokenType.NAME).value
        self.expect(TokenType.NEWLINE)
        return ast.Import(name, alias)

    def from_import_stmt(self):
        self.expect(TokenType.FROM)
        module = self.expect(TokenType.NAME).value
        self.expect(TokenType.IMPORT)
        names = []
        n = self.expect(TokenType.NAME).value
        a = None
        if self.match(TokenType.AS):
            a = self.expect(TokenType.NAME).value
        names.append((n, a))
        while self.match(TokenType.COMMA):
            n = self.expect(TokenType.NAME).value
            a = None
            if self.match(TokenType.AS):
                a = self.expect(TokenType.NAME).value
            names.append((n, a))
        self.expect(TokenType.NEWLINE)
        return ast.FromImport(module, names)

    def block(self):
        self.expect(TokenType.NEWLINE)
        self.skip_newlines()
        self.expect(TokenType.INDENT, "expected an indented block")
        stmts = []
        while not self.check(TokenType.DEDENT, TokenType.EOF):
            stmts.append(self.statement())
            self.skip_newlines()
        self.expect(TokenType.DEDENT)
        return stmts

    def if_stmt(self):
        self.expect(TokenType.IF)
        return self._if_tail()

    def _if_tail(self):
        test = self.expr()
        self.expect(TokenType.COLON)
        body = self.block()
        orelse = []
        if self.check(TokenType.ELIF):
            self.advance()
            orelse = [self._if_tail()]
        elif self.match(TokenType.ELSE):
            self.expect(TokenType.COLON)
            orelse = self.block()
        return ast.If(test, body, orelse)

    def while_stmt(self):
        self.expect(TokenType.WHILE)
        test = self.expr()
        self.expect(TokenType.COLON)
        body = self.block()
        return ast.While(test, body)

    def for_stmt(self):
        self.expect(TokenType.FOR)
        target = ast.Name(self.expect(TokenType.NAME).value)
        if self.check(TokenType.COMMA):
            elts = [target]
            while self.match(TokenType.COMMA):
                if self.check(TokenType.IN):
                    break
                elts.append(ast.Name(self.expect(TokenType.NAME).value))
            target = ast.TupleLit(elts)
        self.expect(TokenType.IN)
        iter_ = self.expr()
        self.expect(TokenType.COLON)
        body = self.block()
        return ast.For(target, iter_, body)

    def decorated(self):
        decorators = []
        while self.match(TokenType.AT):
            decorators.append(self.expr())
            self.expect(TokenType.NEWLINE)
            self.skip_newlines()
        if self.check(TokenType.DEF):
            node = self.func_def()
        elif self.check(TokenType.CLASS):
            node = self.class_def()
        else:
            raise self.error("expected 'def' or 'class' after decorator")
        node.decorators = decorators
        return node

    def func_def(self):
        self.expect(TokenType.DEF)
        name = self.expect(TokenType.NAME).value
        self.expect(TokenType.LPAREN)
        params, defaults, vararg, kwarg = [], [], None, None
        if not self.check(TokenType.RPAREN):
            self._parse_param(params, defaults, vararg_kwarg := [None, None])
            while self.match(TokenType.COMMA):
                self._parse_param(params, defaults, vararg_kwarg)
            vararg, kwarg = vararg_kwarg
        self.expect(TokenType.RPAREN)
        self.expect(TokenType.COLON)
        body = self.block()
        return ast.FunctionDef(name, params, defaults, vararg, kwarg, body)

    def _parse_param(self, params, defaults, vararg_kwarg):
        if self.match(TokenType.POWER):
            vararg_kwarg[1] = self.expect(TokenType.NAME).value
            return
        if self.match(TokenType.MULTIPLY):
            vararg_kwarg[0] = self.expect(TokenType.NAME).value
            return
        if vararg_kwarg[0] is not None or vararg_kwarg[1] is not None:
            raise self.error("positional parameter after *args/**kwargs")
        name = self.expect(TokenType.NAME).value
        default = None
        if self.match(TokenType.ASSIGN):
            default = self.expr()
        params.append(name)
        defaults.append(default)

    def class_def(self):
        self.expect(TokenType.CLASS)
        name = self.expect(TokenType.NAME).value
        bases = []
        metaclass = None
        if self.match(TokenType.LPAREN):
            if not self.check(TokenType.RPAREN):
                self._parse_class_arg(bases, lambda m: setattr(self, '_meta', m))
                while self.match(TokenType.COMMA):
                    if self.check(TokenType.RPAREN):
                        break
                    self._parse_class_arg(bases, lambda m: setattr(self, '_meta', m))
            self.expect(TokenType.RPAREN)
            metaclass = getattr(self, '_meta', None)
            if hasattr(self, '_meta'):
                del self._meta
        self.expect(TokenType.COLON)
        body = self.block()
        return ast.ClassDef(name, bases, body, metaclass=metaclass)

    def _parse_class_arg(self, bases, set_meta):
        if (self.check(TokenType.NAME) and self.cur.value == 'metaclass'
                and self.peek(1).type == TokenType.ASSIGN):
            self.advance(); self.advance()
            set_meta(self.expr())
            return
        bases.append(self.expr())

    def with_stmt(self):
        self.expect(TokenType.WITH)
        ctx = self.expr()
        var = None
        if self.match(TokenType.AS):
            var = self.expect(TokenType.NAME).value
        self.expect(TokenType.COLON)
        body = self.block()
        return ast.With(ctx, var, body)

    def try_stmt(self):
        self.expect(TokenType.TRY)
        self.expect(TokenType.COLON)
        body = self.block()
        handlers = []
        while self.check(TokenType.EXCEPT):
            self.advance()
            exc_type = None
            name = None
            if not self.check(TokenType.COLON):
                exc_type = self.expr()
                if self.match(TokenType.AS):
                    name = self.expect(TokenType.NAME).value
            self.expect(TokenType.COLON)
            handlers.append(ast.ExceptHandler(exc_type, name, self.block()))
        finallybody = []
        if self.match(TokenType.FINALLY):
            self.expect(TokenType.COLON)
            finallybody = self.block()
        if not handlers and not finallybody:
            raise self.error("try block must have at least one except or finally")
        return ast.Try(body, handlers, finallybody)

    # ---------- expressions ----------

    def expr(self):
        if self.check(TokenType.LAMBDA):
            return self.lambda_expr()
        node = self.coalesce_expr()
        if self.match(TokenType.IF):
            test = self.coalesce_expr()
            self.expect(TokenType.ELSE)
            orelse = self.expr()
            return ast.IfExpr(node, test, orelse)
        return node

    def coalesce_expr(self):
        """a ?? b — left-associative, looser than pipe."""
        left = self.pipe_expr()
        while self.match(TokenType.NCOALESCE):
            right = self.pipe_expr()
            left = ast.NoneCoalesce(left, right)
        return left

    def pipe_expr(self):
        """Mamba pipe operator. Three forms:

          x |> f                  →  f(x)
          x |> f(a, b)            →  f(a, b, x)        (append by default —
                                                        matches Python stdlib
                                                        like map/filter)
          x |> f(_, b) / f(a, _)  →  every `_` in the args is replaced with x

        Left-associative, low precedence."""
        left = self.or_expr()
        while self.match(TokenType.PIPE):
            right = self.or_expr()
            if isinstance(right, ast.Call):
                # Look for a `_` placeholder in positional args.
                placeholders = [
                    i for i, a in enumerate(right.args)
                    if isinstance(a, ast.Name) and a.name == '_'
                ]
                if placeholders:
                    for i in placeholders:
                        right.args[i] = left
                else:
                    right.args = right.args + [left]
                left = right
            else:
                left = ast.Call(right, [left], [])
        return left

    def lambda_expr(self):
        self.expect(TokenType.LAMBDA)
        params, defaults = [], []
        if not self.check(TokenType.COLON):
            params.append(self.expect(TokenType.NAME).value)
            defaults.append(
                self.expr() if self.match(TokenType.ASSIGN) else None
            )
            while self.match(TokenType.COMMA):
                params.append(self.expect(TokenType.NAME).value)
                defaults.append(
                    self.expr() if self.match(TokenType.ASSIGN) else None
                )
        self.expect(TokenType.COLON)
        # Mamba extension: multi-line lambda body if a newline follows the
        # colon, parse an indented block instead of a single expression.
        if self.check(TokenType.NEWLINE):
            body = self.block()
            self._block_lambda_consumed = True
            return ast.Lambda(params, defaults, body)
        body = self.expr()
        return ast.Lambda(params, defaults, body)

    def _expect_newline_or_block_end(self):
        if self._block_lambda_consumed:
            self._block_lambda_consumed = False
            return
        self.expect(TokenType.NEWLINE)

    def or_expr(self):
        left = self.and_expr()
        while self.match(TokenType.OR):
            left = ast.BoolOp('or', left, self.and_expr())
        return left

    def and_expr(self):
        left = self.not_expr()
        while self.match(TokenType.AND):
            left = ast.BoolOp('and', left, self.not_expr())
        return left

    def not_expr(self):
        if self.match(TokenType.NOT):
            return ast.UnaryOp('not', self.not_expr())
        return self.comparison()

    def comparison(self):
        left = self.add()
        cmp_map = {
            TokenType.EQ: '==', TokenType.NEQ: '!=',
            TokenType.LT: '<', TokenType.GT: '>',
            TokenType.LTE: '<=', TokenType.GTE: '>=',
            TokenType.IS: 'is',
            TokenType.IN: 'in',
        }
        comparisons = []  # list of (op, right)
        while True:
            if self.check(TokenType.NOT) and self.peek(1).type == TokenType.IN:
                self.advance(); self.advance()
                comparisons.append(('not in', self.add()))
                continue
            if self.cur.type in cmp_map:
                op = cmp_map[self.advance().type]
                if op == 'is' and self.match(TokenType.NOT):
                    op = 'is not'
                comparisons.append((op, self.add()))
                continue
            break
        if not comparisons:
            return left
        if len(comparisons) == 1:
            op, right = comparisons[0]
            return ast.Compare(op, left, right)
        # Build (a OP1 b) and (b OP2 c) and ...
        result = None
        prev = left
        for op, right in comparisons:
            piece = ast.Compare(op, prev, right)
            result = piece if result is None else ast.BoolOp('and', result, piece)
            prev = right
        return result

    def add(self):
        left = self.mul()
        while self.cur.type in (TokenType.PLUS, TokenType.MINUS):
            op = '+' if self.advance().type == TokenType.PLUS else '-'
            left = ast.BinOp(op, left, self.mul())
        return left

    def mul(self):
        left = self.unary()
        while self.cur.type in (TokenType.MULTIPLY, TokenType.DIVIDE,
                                TokenType.MOD, TokenType.FLOORDIV):
            tt = self.advance().type
            op = {TokenType.MULTIPLY: '*', TokenType.DIVIDE: '/',
                  TokenType.MOD: '%', TokenType.FLOORDIV: '//'}[tt]
            left = ast.BinOp(op, left, self.unary())
        return left

    def unary(self):
        if self.match(TokenType.MINUS):
            return ast.UnaryOp('-', self.unary())
        if self.match(TokenType.PLUS):
            return ast.UnaryOp('+', self.unary())
        return self.power()

    def power(self):
        left = self.trailer()
        if self.match(TokenType.POWER):
            return ast.BinOp('**', left, self.unary())  # right-assoc
        return left

    def trailer(self):
        node = self.atom()
        while True:
            if self.match(TokenType.LPAREN):
                args, kwargs = [], []
                if not self.check(TokenType.RPAREN):
                    self._parse_call_arg(args, kwargs)
                    while self.match(TokenType.COMMA):
                        if self.check(TokenType.RPAREN):
                            break
                        self._parse_call_arg(args, kwargs)
                self.expect(TokenType.RPAREN)
                node = ast.Call(node, args, kwargs)
            elif self.match(TokenType.LBRACK):
                node = ast.Subscript(node, self._parse_subscript())
                self.expect(TokenType.RBRACK)
            elif self.match(TokenType.DOT):
                attr = self.expect(TokenType.NAME).value
                node = ast.Attribute(node, attr)
            else:
                break
        return node

    def _parse_call_arg(self, args, kwargs):
        # **expr → kwargs unpacking
        if self.match(TokenType.POWER):
            kwargs.append((None, self.expr()))
            return
        # *expr → args unpacking
        if self.match(TokenType.MULTIPLY):
            args.append(ast.Starred(self.expr()))
            return
        # NAME = expr  → keyword arg
        if (self.check(TokenType.NAME)
                and self.peek(1).type == TokenType.ASSIGN):
            name = self.advance().value
            self.advance()  # =
            kwargs.append((name, self.expr()))
            return
        args.append(self.expr())

    def _parse_comp_clauses(self, end_tok):
        gens = []
        while self.match(TokenType.FOR):
            target = ast.Name(self.expect(TokenType.NAME).value)
            if self.check(TokenType.COMMA):
                elts = [target]
                while self.match(TokenType.COMMA):
                    if self.check(TokenType.IN):
                        break
                    elts.append(ast.Name(self.expect(TokenType.NAME).value))
                target = ast.TupleLit(elts)
            self.expect(TokenType.IN)
            iter_ = self.or_expr()  # avoid swallowing trailing 'for' / 'if'
            ifs = []
            while self.match(TokenType.IF):
                ifs.append(self.or_expr())
            gens.append(ast.CompFor(target, iter_, ifs))
        return gens

    def _parse_subscript(self):
        # supports: expr | [expr]:[expr][:[expr]]
        start = stop = step = None
        is_slice = False
        if not self.check(TokenType.COLON):
            start = self.expr()
        if self.match(TokenType.COLON):
            is_slice = True
            if not self.check(TokenType.COLON, TokenType.RBRACK):
                stop = self.expr()
            if self.match(TokenType.COLON):
                if not self.check(TokenType.RBRACK):
                    step = self.expr()
        if is_slice:
            return ast.Slice(start, stop, step)
        return start

    def atom(self):
        tok = self.cur
        if tok.type == TokenType.NUMBER:
            self.advance(); return ast.Num(tok.value)
        if tok.type == TokenType.STRING:
            self.advance(); return ast.Str(tok.value)
        if tok.type == TokenType.FSTRING:
            self.advance()
            from .lexer import Lexer
            segs = []
            for kind, payload in tok.value:
                if kind == 'text':
                    segs.append(('text', payload))
                else:
                    sub_tokens = Lexer(payload + "\n").tokenize()
                    sub = Parser(sub_tokens, source=payload, file=self.file)
                    segs.append(('expr', sub.expr()))
            return ast.FString(segs)
        if tok.type == TokenType.TRUE:
            self.advance(); return ast.Bool(True)
        if tok.type == TokenType.FALSE:
            self.advance(); return ast.Bool(False)
        if tok.type == TokenType.NONE:
            self.advance(); return ast.NoneLit()
        if tok.type == TokenType.NAME:
            self.advance(); return ast.Name(tok.value)
        if tok.type == TokenType.LPAREN:
            self.advance()
            if self.match(TokenType.RPAREN):
                return ast.TupleLit([])
            e = self.expr()
            if self.match(TokenType.COMMA):
                elts = [e]
                if not self.check(TokenType.RPAREN):
                    elts.append(self.expr())
                    while self.match(TokenType.COMMA):
                        if self.check(TokenType.RPAREN):
                            break
                        elts.append(self.expr())
                self.expect(TokenType.RPAREN)
                return ast.TupleLit(elts)
            self.expect(TokenType.RPAREN)
            return e
        if tok.type == TokenType.LBRACK:
            self.advance()
            if self.match(TokenType.RBRACK):
                return ast.ListLit([])
            first = self._parse_starred_or_expr()
            if self.check(TokenType.FOR) and not isinstance(first, ast.Starred):
                gens = self._parse_comp_clauses(TokenType.RBRACK)
                self.expect(TokenType.RBRACK)
                return ast.ListComp(first, gens)
            elts = [first]
            while self.match(TokenType.COMMA):
                if self.check(TokenType.RBRACK):
                    break
                elts.append(self._parse_starred_or_expr())
            self.expect(TokenType.RBRACK)
            return ast.ListLit(elts)
        if tok.type == TokenType.LBRACE:
            self.advance()
            if self.match(TokenType.RBRACE):
                return ast.DictLit([])
            # **expr at start → dict
            if self.match(TokenType.POWER):
                pairs = [(None, self.expr())]
                while self.match(TokenType.COMMA):
                    if self.check(TokenType.RBRACE):
                        break
                    if self.match(TokenType.POWER):
                        pairs.append((None, self.expr()))
                    else:
                        k = self.expr()
                        self.expect(TokenType.COLON)
                        v = self.expr()
                        pairs.append((k, v))
                self.expect(TokenType.RBRACE)
                return ast.DictLit(pairs)
            first = self._parse_starred_or_expr()
            if self.match(TokenType.COLON):
                first_v = self.expr()
                if self.check(TokenType.FOR):
                    gens = self._parse_comp_clauses(TokenType.RBRACE)
                    self.expect(TokenType.RBRACE)
                    return ast.DictComp(first, first_v, gens)
                pairs = [(first, first_v)]
                while self.match(TokenType.COMMA):
                    if self.check(TokenType.RBRACE):
                        break
                    if self.match(TokenType.POWER):
                        pairs.append((None, self.expr()))
                    else:
                        k = self.expr()
                        self.expect(TokenType.COLON)
                        v = self.expr()
                        pairs.append((k, v))
                self.expect(TokenType.RBRACE)
                return ast.DictLit(pairs)
            # set literal or set comprehension
            if self.check(TokenType.FOR) and not isinstance(first, ast.Starred):
                gens = self._parse_comp_clauses(TokenType.RBRACE)
                self.expect(TokenType.RBRACE)
                return ast.SetComp(first, gens)
            elts = [first]
            while self.match(TokenType.COMMA):
                if self.check(TokenType.RBRACE):
                    break
                elts.append(self._parse_starred_or_expr())
            self.expect(TokenType.RBRACE)
            return ast.SetLit(elts)

    def _parse_starred_or_expr(self):
        if self.match(TokenType.MULTIPLY):
            return ast.Starred(self.expr())
        return self.expr()
        raise self.error(
            f"unexpected token {tok.type.name} ({tok.value!r})"
        )
