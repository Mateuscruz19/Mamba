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
    EQUAL = auto()
    # delimiters
    LPAREN = auto()
    RPAREN = auto()
    COLON = auto()
    NEWLINE = auto()
    # special
    EOF = auto()


KEYWORDS = {
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

    def advance(self):
        """Move to the next character."""
        self.pos += 1
        if self.pos < len(self.source):
            self.current_char = self.source[self.pos]
        else:
            self.current_char = None

    def skip_whitespace(self):
        """Skip spaces and tabs (NOT newlines — those are tokens)."""
        while self.current_char is not None and self.current_char in ' \t':
            self.advance()

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
        """Read a string literal between quotes."""
        quote_char = self.current_char  # remembers if it was ' or "
        self.advance()  # skip the opening quote
        result = ''

        while self.current_char is not None and self.current_char != quote_char:
            result += self.current_char
            self.advance()

        if self.current_char is None:
            raise SyntaxError(f"Unterminated string on line {self.line}")

        self.advance()  # skip the closing quote
        return Token(TokenType.STRING, result, self.line)

    def read_word(self):
        """Read a word (variable name or keyword)."""
        result = ''
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == '_'):
            result += self.current_char
            self.advance()

        # Check if it's a keyword, otherwise it's a NAME
        token_type = KEYWORDS.get(result, TokenType.NAME)
        return Token(token_type, result, self.line)

    def tokenize(self):
        """Scan the entire source and return a list of tokens."""
        tokens = []

        while self.current_char is not None:
            # Skip spaces and tabs
            if self.current_char in ' \t':
                self.skip_whitespace()
                continue

            # Newlines
            if self.current_char == '\n':
                tokens.append(Token(TokenType.NEWLINE, '\\n', self.line))
                self.line += 1
                self.advance()
                continue

            # Numbers: starts with a digit → read the full number
            if self.current_char.isdigit():
                tokens.append(self.read_number())
                continue

            # Strings: starts with a quote → read until closing quote
            if self.current_char in '"\'':
                tokens.append(self.read_string())
                continue

            # Words: starts with a letter or _ → could be a name or keyword
            if self.current_char.isalpha() or self.current_char == '_':
                tokens.append(self.read_word())
                continue

            # Single-character tokens
            if self.current_char == '+':
                tokens.append(Token(TokenType.PLUS, '+', self.line))
                self.advance()
            elif self.current_char == '-':
                tokens.append(Token(TokenType.MINUS, '-', self.line))
                self.advance()
            elif self.current_char == '*':
                tokens.append(Token(TokenType.MULTIPLY, '*', self.line))
                self.advance()
            elif self.current_char == '/':
                tokens.append(Token(TokenType.DIVIDE, '/', self.line))
                self.advance()
            elif self.current_char == '=':
                tokens.append(Token(TokenType.EQUAL, '=', self.line))
                self.advance()
            elif self.current_char == '(':
                tokens.append(Token(TokenType.LPAREN, '(', self.line))
                self.advance()
            elif self.current_char == ')':
                tokens.append(Token(TokenType.RPAREN, ')', self.line))
                self.advance()
            elif self.current_char == ':':
                tokens.append(Token(TokenType.COLON, ':', self.line))
                self.advance()
            else:
                raise SyntaxError(f"Unknown character '{self.current_char}' on line {self.line}")

        tokens.append(Token(TokenType.EOF, None, self.line))
        return tokens
