import unittest

from src.lexer import Lexer, TokenType


def types(src):
    return [t.type for t in Lexer(src).tokenize()]


class LexerTests(unittest.TestCase):
    def test_numbers_and_operators(self):
        toks = Lexer("1 + 2 * 3.5\n").tokenize()
        self.assertEqual(toks[0].type, TokenType.NUMBER)
        self.assertEqual(toks[0].value, 1)
        self.assertEqual(toks[4].value, 3.5)

    def test_string_single_and_double(self):
        self.assertEqual(Lexer('"hi"\n').tokenize()[0].value, "hi")
        self.assertEqual(Lexer("'hi'\n").tokenize()[0].value, "hi")

    def test_keywords(self):
        ts = types("if x:\n    pass\n")
        self.assertIn(TokenType.IF, ts)
        self.assertIn(TokenType.PASS, ts)
        self.assertIn(TokenType.INDENT, ts)
        self.assertIn(TokenType.DEDENT, ts)

    def test_compound_operators(self):
        ts = types("a == b != c <= d >= e\n")
        for t in (TokenType.EQ, TokenType.NEQ, TokenType.LTE, TokenType.GTE):
            self.assertIn(t, ts)

    def test_indent_dedent_balance(self):
        src = "def f():\n    if 1:\n        pass\n"
        ts = types(src)
        n_in = ts.count(TokenType.INDENT)
        n_de = ts.count(TokenType.DEDENT)
        self.assertEqual(n_in, n_de)

    def test_paren_suppresses_newline(self):
        # Newline inside parens should not break the call
        ts = types("f(1,\n  2)\n")
        # only one NEWLINE (the trailing one)
        self.assertEqual(ts.count(TokenType.NEWLINE), 1)

    def test_comment_skipped(self):
        ts = types("x = 1  # a comment\n")
        self.assertNotIn(None, ts)


if __name__ == "__main__":
    unittest.main()
