"""Phase D tests: Elm-style error messages, did-you-mean suggestions,
contextual syntax hints."""

import unittest

from src.lexer import Lexer
from src.parser import Parser
from src.interpreter import Interpreter
from src.errors import MambaSyntaxError, suggest


class SuggestTests(unittest.TestCase):
    def test_close_match(self):
        self.assertEqual(suggest("counter", ["count", "counter_2", "ctr"]), "count")

    def test_no_match_when_far(self):
        self.assertIsNone(suggest("zzzzz", ["foo", "bar"]))

    def test_empty_query(self):
        self.assertIsNone(suggest("", ["foo"]))


class DidYouMeanTests(unittest.TestCase):
    def test_name_error_suggests_local(self):
        src = (
            "counter = 0\n"
            "def inc():\n"
            "    global counter\n"
            "    countr + 1\n"
            "inc()\n"
        )
        try:
            Interpreter().run(Parser(Lexer(src).tokenize()).parse())
            self.fail("expected NameError")
        except NameError as e:
            self.assertIn("counter", str(e))
            self.assertIn("did you mean", str(e))

    def test_attr_error_suggests_method(self):
        src = (
            "class C:\n"
            "    def hello(self):\n"
            "        return 1\n"
            "C().helo()\n"
        )
        try:
            Interpreter().run(Parser(Lexer(src).tokenize()).parse())
            self.fail("expected AttributeError")
        except AttributeError as e:
            self.assertIn("hello", str(e))
            self.assertIn("did you mean", str(e))

    def test_python_obj_attr_suggestion(self):
        src = "'hi'.uppr()\n"
        try:
            Interpreter().run(Parser(Lexer(src).tokenize()).parse())
            self.fail("expected AttributeError")
        except AttributeError as e:
            self.assertIn("upper", str(e))


class FormatterTests(unittest.TestCase):
    def test_format_includes_context_lines(self):
        src = "x = 1\nif x\n    print(x)\n"
        try:
            Parser(Lexer(src).tokenize(), source=src).parse()
            self.fail("expected error")
        except MambaSyntaxError as e:
            out = e.format(color=False)
            self.assertIn("if x", out)
            self.assertIn("x = 1", out)
            self.assertIn("SYNTAX ERROR", out)
            self.assertIn("help:", out)

    def test_missing_colon_hint(self):
        src = "if 1\n    pass\n"
        try:
            Parser(Lexer(src).tokenize(), source=src).parse()
            self.fail("expected error")
        except MambaSyntaxError as e:
            self.assertIn("`:`", e.format(color=False))

    def test_unbalanced_paren_hint(self):
        src = "x = (1 + 2\ny = 3\n"
        try:
            Parser(Lexer(src).tokenize(), source=src).parse()
            self.fail("expected error")
        except MambaSyntaxError as e:
            self.assertIn("parenthes", e.format(color=False).lower())


if __name__ == "__main__":
    unittest.main()
