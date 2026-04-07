from enum import Enum, auto


class TokenType(Enum):
    # literals
    NUMBER = auto()
    STRING = auto()
    NAME = auto()
    # operators
    PLUS = auto()
    MINUS = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    ASSIGN = auto()       # =
    EQ = auto()           # ==
    NEQ = auto()          # !=
    LT = auto()
    GT = auto()
    LTE = auto()
    GTE = auto()
    POWER = auto()        # **
    MOD = auto()          # %
    FLOORDIV = auto()     # //
    PLUS_EQ = auto()
    MINUS_EQ = auto()
    STAR_EQ = auto()
    SLASH_EQ = auto()
    MOD_EQ = auto()
    FSTRING = auto()
    # delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACK = auto()
    RBRACK = auto()
    LBRACE = auto()
    RBRACE = auto()
    COMMA = auto()
    DOT = auto()
    COLON = auto()
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    # keywords
    IF = auto()
    ELIF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    IN = auto()
    DEF = auto()
    RETURN = auto()
    PASS = auto()
    BREAK = auto()
    CONTINUE = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    TRUE = auto()
    FALSE = auto()
    NONE = auto()
    CLASS = auto()
    TRY = auto()
    EXCEPT = auto()
    FINALLY = auto()
    RAISE = auto()
    IMPORT = auto()
    FROM = auto()
    AS = auto()
    IS = auto()
    LAMBDA = auto()
    YIELD = auto()
    WITH = auto()
    GLOBAL = auto()
    NONLOCAL = auto()
    AT = auto()
    ASSERT = auto()
    DEL = auto()
    PIPE = auto()  # |>  (Mamba pipe operator)
    NCOALESCE = auto()  # ??  (Mamba none-coalescing)
    QDOT = auto()       # ?.  (Mamba optional chaining attribute)
    QLBRACK = auto()    # ?[  (Mamba optional chaining subscript)
    # special
    EOF = auto()


KEYWORDS = {
    'if': TokenType.IF,
    'elif': TokenType.ELIF,
    'else': TokenType.ELSE,
    'while': TokenType.WHILE,
    'for': TokenType.FOR,
    'in': TokenType.IN,
    'def': TokenType.DEF,
    'return': TokenType.RETURN,
    'pass': TokenType.PASS,
    'break': TokenType.BREAK,
    'continue': TokenType.CONTINUE,
    'and': TokenType.AND,
    'or': TokenType.OR,
    'not': TokenType.NOT,
    'True': TokenType.TRUE,
    'False': TokenType.FALSE,
    'None': TokenType.NONE,
    'class': TokenType.CLASS,
    'try': TokenType.TRY,
    'except': TokenType.EXCEPT,
    'finally': TokenType.FINALLY,
    'raise': TokenType.RAISE,
    'import': TokenType.IMPORT,
    'from': TokenType.FROM,
    'as': TokenType.AS,
    'is': TokenType.IS,
    'lambda': TokenType.LAMBDA,
    'yield': TokenType.YIELD,
    'with': TokenType.WITH,
    'global': TokenType.GLOBAL,
    'nonlocal': TokenType.NONLOCAL,
    'assert': TokenType.ASSERT,
    'del': TokenType.DEL,
}


class Token:
    def __init__(self, type: TokenType, value=None, line: int = 0):
        self.type = type
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, line={self.line})"


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.current_char = self.source[0] if source else None
        self.indent_stack = [0]
        self.paren_depth = 0  # newlines/indents are ignored inside (), [], {}

    def advance(self):
        """Move to the next character."""
        self.pos += 1
        if self.pos < len(self.source):
            self.current_char = self.source[self.pos]
        else:
            self.current_char = None

    def peek(self, offset: int = 1):
        p = self.pos + offset
        return self.source[p] if p < len(self.source) else None

    def skip_whitespace(self):
        """Skip spaces and tabs (NOT newlines — those are tokens)."""
        while self.current_char is not None and self.current_char in ' \t':
            self.advance()

    def skip_comment(self):
        """Skip from # to end of line (newline itself stays)."""
        while self.current_char is not None and self.current_char != '\n':
            self.advance()

    def skip_block_comment(self):
        """Skip /* ... */ — supports nesting and multi-line."""
        # we're sitting on the '/'; consume '/' and '*'
        self.advance(); self.advance()
        depth = 1
        while self.current_char is not None and depth > 0:
            if self.current_char == '/' and self.peek() == '*':
                self.advance(); self.advance()
                depth += 1
                continue
            if self.current_char == '*' and self.peek() == '/':
                self.advance(); self.advance()
                depth -= 1
                continue
            if self.current_char == '\n':
                self.line += 1
            self.advance()
        if depth > 0:
            raise SyntaxError(
                f"Unterminated block comment starting near line {self.line}"
            )

    def read_number(self):
        """Read a full number (int or float)."""
        result = ''
        while self.current_char is not None and self.current_char.isdigit():
            result += self.current_char
            self.advance()

        # Check for decimal point (3.14)
        if self.current_char == '.':
            result += '.'
            self.advance()
            while self.current_char is not None and self.current_char.isdigit():
                result += self.current_char
                self.advance()
            return Token(TokenType.NUMBER, float(result), self.line)

        return Token(TokenType.NUMBER, int(result), self.line)

    def read_string(self):
        """Read a string literal between quotes, processing escape sequences."""
        quote_char = self.current_char  # remembers if it was ' or "
        self.advance()  # skip the opening quote
        result = ''
        escapes = {'n': '\n', 't': '\t', 'r': '\r', '0': '\0',
                   '\\': '\\', "'": "'", '"': '"'}

        while self.current_char is not None and self.current_char != quote_char:
            if self.current_char == '\\':
                self.advance()
                ch = self.current_char
                if ch is None:
                    break
                result += escapes.get(ch, '\\' + ch)
                self.advance()
            else:
                result += self.current_char
                self.advance()

        if self.current_char is None:
            raise SyntaxError(f"Unterminated string on line {self.line}")

        self.advance()  # skip the closing quote
        return Token(TokenType.STRING, result, self.line)

    def read_fstring(self):
        """Read an f-string into a list of ('text'|'expr', payload) segments."""
        quote = self.current_char
        self.advance()
        segments = []
        text = ''
        while self.current_char is not None and self.current_char != quote:
            ch = self.current_char
            if ch == '{':
                if self.peek() == '{':
                    text += '{'
                    self.advance(); self.advance()
                    continue
                if text:
                    segments.append(('text', text)); text = ''
                self.advance()  # skip {
                depth = 1
                expr = ''
                while self.current_char is not None and depth > 0:
                    if self.current_char == '{':
                        depth += 1
                    elif self.current_char == '}':
                        depth -= 1
                        if depth == 0:
                            break
                    expr += self.current_char
                    self.advance()
                if self.current_char != '}':
                    raise SyntaxError(f"unterminated f-string expression on line {self.line}")
                self.advance()  # skip }
                segments.append(('expr', expr))
            elif ch == '}':
                if self.peek() == '}':
                    text += '}'
                    self.advance(); self.advance()
                    continue
                raise SyntaxError(f"single '}}' in f-string on line {self.line}")
            elif ch == '\\':
                # minimal escape handling
                self.advance()
                esc = self.current_char
                text += {'n': '\n', 't': '\t', 'r': '\r',
                         '\\': '\\', "'": "'", '"': '"'}.get(esc, esc or '')
                if self.current_char is not None:
                    self.advance()
            else:
                text += ch
                self.advance()
        if self.current_char is None:
            raise SyntaxError(f"unterminated f-string on line {self.line}")
        self.advance()  # closing quote
        if text:
            segments.append(('text', text))
        return Token(TokenType.FSTRING, segments, self.line)

    def read_word(self):
        """Read a word (variable name or keyword)."""
        result = ''
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == '_'):
            result += self.current_char
            self.advance()

        # Check if it's a keyword, otherwise it's a NAME
        token_type = KEYWORDS.get(result, TokenType.NAME)
        return Token(token_type, result, self.line)

    def handle_line_start(self, tokens):
        """At the start of a logical line, measure indentation and emit
        INDENT/DEDENT tokens. Skips fully blank/comment-only lines."""
        while True:
            indent = 0
            while self.current_char == ' ':
                indent += 1
                self.advance()
            while self.current_char == '\t':
                indent += 8 - (indent % 8)
                self.advance()

            # Blank line or comment-only line: skip without emitting indents
            if self.current_char == '\n':
                self.line += 1
                self.advance()
                continue
            if self.current_char == '#':
                self.skip_comment()
                continue
            if self.current_char is None:
                return

            top = self.indent_stack[-1]
            if indent > top:
                self.indent_stack.append(indent)
                tokens.append(Token(TokenType.INDENT, indent, self.line))
            else:
                while indent < self.indent_stack[-1]:
                    self.indent_stack.pop()
                    tokens.append(Token(TokenType.DEDENT, None, self.line))
                if indent != self.indent_stack[-1]:
                    raise SyntaxError(
                        f"Inconsistent indentation on line {self.line}"
                    )
            return

    def tokenize(self):
        """Scan the entire source and return a list of tokens."""
        tokens = []
        at_line_start = True

        while self.current_char is not None:
            if at_line_start and self.paren_depth == 0:
                self.handle_line_start(tokens)
                at_line_start = False
                if self.current_char is None:
                    break

            # Spaces/tabs in the middle of a line
            if self.current_char in ' \t':
                self.skip_whitespace()
                continue

            # Comments
            if self.current_char == '#':
                self.skip_comment()
                continue

            # Block comments /* ... */ (Mamba extension)
            if self.current_char == '/' and self.peek() == '*':
                self.skip_block_comment()
                continue

            # Line continuation: backslash before newline
            if self.current_char == '\\' and self.peek() == '\n':
                self.advance()
                self.advance()
                self.line += 1
                continue

            # Newlines
            if self.current_char == '\n':
                if self.paren_depth == 0:
                    # Avoid duplicate NEWLINE tokens
                    if tokens and tokens[-1].type != TokenType.NEWLINE:
                        tokens.append(Token(TokenType.NEWLINE, '\\n', self.line))
                    at_line_start = True
                self.line += 1
                self.advance()
                continue

            # Numbers
            if self.current_char.isdigit():
                tokens.append(self.read_number())
                continue

            # f-strings: f"..." or f'...'
            if self.current_char in 'fF' and self.peek() in '"\'':
                self.advance()
                tokens.append(self.read_fstring())
                continue

            # Strings
            if self.current_char in '"\'':
                tokens.append(self.read_string())
                continue

            # Identifiers / keywords
            if self.current_char.isalpha() or self.current_char == '_':
                word_tok = self.read_word()
                # read_word currently sets type via KEYWORDS dict, but it
                # also stores the raw string as value — for keyword tokens
                # we keep that as the lexeme.
                tokens.append(word_tok)
                continue

            ch = self.current_char

            # Two-character operators first
            if ch == '=' and self.peek() == '=':
                tokens.append(Token(TokenType.EQ, '==', self.line))
                self.advance(); self.advance()
                continue
            if ch == '!' and self.peek() == '=':
                tokens.append(Token(TokenType.NEQ, '!=', self.line))
                self.advance(); self.advance()
                continue
            if ch == '<' and self.peek() == '=':
                tokens.append(Token(TokenType.LTE, '<=', self.line))
                self.advance(); self.advance()
                continue
            if ch == '>' and self.peek() == '=':
                tokens.append(Token(TokenType.GTE, '>=', self.line))
                self.advance(); self.advance()
                continue
            if ch == '*' and self.peek() == '*':
                tokens.append(Token(TokenType.POWER, '**', self.line))
                self.advance(); self.advance()
                continue
            if ch == '/' and self.peek() == '/':
                tokens.append(Token(TokenType.FLOORDIV, '//', self.line))
                self.advance(); self.advance()
                continue
            if ch == '|' and self.peek() == '>':
                tokens.append(Token(TokenType.PIPE, '|>', self.line))
                self.advance(); self.advance()
                continue
            if ch == '?' and self.peek() == '?':
                tokens.append(Token(TokenType.NCOALESCE, '??', self.line))
                self.advance(); self.advance()
                continue
            if ch == '?' and self.peek() == '.':
                tokens.append(Token(TokenType.QDOT, '?.', self.line))
                self.advance(); self.advance()
                continue
            if ch == '?' and self.peek() == '[':
                tokens.append(Token(TokenType.QLBRACK, '?[', self.line))
                self.paren_depth += 1
                self.advance(); self.advance()
                continue
            two_char_aug = {
                '+=': TokenType.PLUS_EQ, '-=': TokenType.MINUS_EQ,
                '*=': TokenType.STAR_EQ, '/=': TokenType.SLASH_EQ,
                '%=': TokenType.MOD_EQ,
            }
            pair = ch + (self.peek() or '')
            if pair in two_char_aug:
                tokens.append(Token(two_char_aug[pair], pair, self.line))
                self.advance(); self.advance()
                continue

            single = {
                '+': TokenType.PLUS,
                '-': TokenType.MINUS,
                '*': TokenType.MULTIPLY,
                '/': TokenType.DIVIDE,
                '=': TokenType.ASSIGN,
                '<': TokenType.LT,
                '>': TokenType.GT,
                '(': TokenType.LPAREN,
                ')': TokenType.RPAREN,
                '[': TokenType.LBRACK,
                ']': TokenType.RBRACK,
                '{': TokenType.LBRACE,
                '}': TokenType.RBRACE,
                ',': TokenType.COMMA,
                '.': TokenType.DOT,
                ':': TokenType.COLON,
                '%': TokenType.MOD,
                '@': TokenType.AT,
            }
            if ch in single:
                tt = single[ch]
                if tt in (TokenType.LPAREN, TokenType.LBRACK, TokenType.LBRACE):
                    self.paren_depth += 1
                elif tt in (TokenType.RPAREN, TokenType.RBRACK, TokenType.RBRACE):
                    self.paren_depth = max(0, self.paren_depth - 1)
                tokens.append(Token(tt, ch, self.line))
                self.advance()
                continue

            raise SyntaxError(f"Unknown character {ch!r} on line {self.line}")

        # Final NEWLINE for the last line if missing
        if tokens and tokens[-1].type != TokenType.NEWLINE:
            tokens.append(Token(TokenType.NEWLINE, '\\n', self.line))

        # Close any remaining open indentation blocks
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            tokens.append(Token(TokenType.DEDENT, None, self.line))

        tokens.append(Token(TokenType.EOF, None, self.line))
        return tokens
