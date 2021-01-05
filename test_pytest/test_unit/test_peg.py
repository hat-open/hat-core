import functools
import pytest

import hat.peg


def test_example():
    grammar = hat.peg.Grammar(r'''
        Expr    <- Sum
        Sum     <- Product (('+' / '-') Product)*
        Product <- Value (('*' / '/') Value)*
        Value   <- Spacing ([0-9]+ / '(' Expr ')') Spacing
        Spacing <- ' '*
    ''', 'Expr')
    ast = grammar.parse('1 + 2 * 3 + (4 - 5) * 6 + 7')
    result = hat.peg.walk_ast(ast, {
        'Expr': lambda n, c: c[0],
        'Sum': lambda n, c: functools.reduce(
            (lambda acc, x: acc + x[1] if x[0] == '+' else acc - x[1]),
            zip(c[1::2], c[2::2]),
            c[0]),
        'Product': lambda n, c: functools.reduce(
            (lambda acc, x: acc * x[1] if x[0] == '*' else acc / x[1]),
            zip(c[1::2], c[2::2]),
            c[0]),
        'Value': lambda n, c: (c[2] if c[1] == '(' else
                               int(''.join(c[1:-1])))})
    assert result == 8


@pytest.mark.parametrize("grammar, starting", [
    (r"x -> 'x'", 'x')
])
def test_invalid_grammar(grammar, starting):
    with pytest.raises(Exception):
        hat.peg.Grammar(grammar, starting)


def test_simple_grammar():
    grammar = hat.peg.Grammar("X <- 'x'", 'X')
    assert len(grammar.definitions) == 1
    assert grammar.starting == 'X'


def test_infinite_recursion_detection():
    grammar = hat.peg.Grammar('x <- x', 'x')
    with pytest.raises(Exception):
        grammar.parse("")


def test_and():
    grammar = hat.peg.Grammar("X <- 'x' & 'y'", 'X')
    node = grammar.parse('xy')
    assert node == hat.peg.Node('X', ['x'])


def test_debug_cb():

    def debug_cb(result, call_stack):
        assert result.node == hat.peg.Node('X', ['x'])
        assert result.rest == ''
        assert len(list(call_stack)) == 1

    grammar = hat.peg.Grammar("X <- 'x'", 'X')
    grammar.parse('x', debug_cb)
