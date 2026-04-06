import unittest

from src.lexer import Lexer
from src.parser import Parser
from src import ast_nodes as ast


def parse(src):
    return Parser(Lexer(src).tokenize()).parse()


class ParserTests(unittest.TestCase):
    def test_assignment(self):
        m = parse("x = 1 + 2\n")
        self.assertIsInstance(m.body[0], ast.Assign)
        self.assertIsInstance(m.body[0].value, ast.BinOp)

    def test_precedence(self):
        m = parse("x = 1 + 2 * 3\n")
        binop = m.body[0].value
        self.assertEqual(binop.op, '+')
        self.assertEqual(binop.right.op, '*')

    def test_if_elif_else(self):
        m = parse("if x:\n    a = 1\nelif y:\n    a = 2\nelse:\n    a = 3\n")
        node = m.body[0]
        self.assertIsInstance(node, ast.If)
        self.assertIsInstance(node.orelse[0], ast.If)

    def test_function_def(self):
        m = parse("def add(a, b):\n    return a + b\n")
        fn = m.body[0]
        self.assertIsInstance(fn, ast.FunctionDef)
        self.assertEqual(fn.params, ['a', 'b'])
        self.assertIsInstance(fn.body[0], ast.Return)

    def test_call(self):
        m = parse("print(1, 2)\n")
        call = m.body[0].expr
        self.assertIsInstance(call, ast.Call)
        self.assertEqual(len(call.args), 2)

    def test_while(self):
        m = parse("while i < 10:\n    i = i + 1\n")
        self.assertIsInstance(m.body[0], ast.While)


if __name__ == "__main__":
    unittest.main()
