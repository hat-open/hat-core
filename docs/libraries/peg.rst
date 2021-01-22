.. _hat-peg:

`hat.peg` - Python parsing expression grammar library
=====================================================

This library provides Python implementation of `Parsing Expression
Grammar <https://en.wikipedia.org/wiki/Parsing_expression_grammar>`_ parser.

Supported PEG grammar is defined by PEG grammar::

    # Hierarchical syntax
    Grammar    <- Spacing Definition+ EndOfFile
    Definition <- Identifier LEFTARROW Expression
    Expression <- Sequence (SLASH Sequence)*
    Sequence   <- Prefix*
    Prefix     <- (AND / NOT)? Suffix
    Suffix     <- Primary (QUESTION / STAR / PLUS)?
    Primary    <- Identifier !LEFTARROW
                / OPEN Expression CLOSE
                / Literal
                / Class
                / DOT

    # Lexical syntax
    Identifier <- IdentStart IdentCont* Spacing
    IdentStart <- [a-zA-Z_]
    IdentCont  <- IdentStart / [0-9]
    Literal    <- ['] (!['] Char)* ['] Spacing
                / ["] (!["] Char)* ["] Spacing
    Class      <- '[' (!']' Range)* ']' Spacing
    Range      <- Char '-' Char / Char
    Char       <- '\\' [nrt'"\[\]\\]
                / '\\' 'x' Hex Hex
                / '\\' 'u' Hex Hex Hex Hex
                / !'\\' .
    Hex        <- [0-9a-fA-F]

    LEFTARROW  <- '<-' Spacing
    SLASH      <- '/' Spacing
    AND        <- '&' Spacing
    NOT        <- '!' Spacing
    QUESTION   <- '?' Spacing
    STAR       <- '*' Spacing
    PLUS       <- '+' Spacing
    OPEN       <- '(' Spacing
    CLOSE      <- ')' Spacing
    DOT        <- '.' Spacing

    Spacing    <- (Space / Comment)*
    Comment    <- '#' (!EndOfLine .)* EndOfLine
    Space      <- ' ' / '\t' / EndOfLine
    EndOfLine  <- '\r\n' / '\n' / '\r'
    EndOfFile  <- !.

`hat.peg.Grammar` can be initialized with string representation of arbitrary
valid PEG grammar. Once instance of this class is initialized, `parse` method
is used for constructing parse tree based on input string data::

    class Node(typing.NamedTuple):
        name: str
        value: typing.List[typing.Union['Node', str]]

    class Grammar:

        def __init__(self,
                     definitions: typing.Union[str,
                                               typing.Dict[str, Expression]],
                     starting: str): ...

        @property
        def definitions(self) -> typing.Dict[str, Expression]: ...

        @property
        def starting(self) -> str: ...

        def parse(self,
                  data: str,
                  debug_cb: typing.Optional[DebugCb] = None
                  ) -> Node: ...

`hat.peg.walk_ast` is utility function providing simple depth-first
abstract syntax tree parser::

    Action = typing.Callable[[Node, typing.List], typing.Any]

    def walk_ast(node: Node,
                 actions: typing.Dict[str, Action],
                 default_action: typing.Optional[Action] = None
                 ) -> typing.Any: ...

Example usage::

    import functools
    import hat.peg

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


API
---

API reference is available as part of generated documentation:

    * `Python hat.peg module <../pyhat/hat/peg.html>`_
