Hat Core - Parsing expression grammar
=====================================

This library is part of Hat Open project - open-source framework of tools and
libraries for developing applications used for remote monitoring, control and
management of intelligent electronic devices such as IoT devices, PLCs,
industrial automation or home automation systems.

Development of Hat Open and associated repositories is sponsored by
Končar - Power Plant and Electric Traction Engineering Inc.
(Končar KET - `<https://www.koncar-ket.hr>`_).

For more information see:

    * `hat-peg` documentation - `<https://core.hat-open.com/docs/libraries/peg.html>`_
    * Hat Core homepage - `<https://core.hat-open.com>`_
    * Hat Core git repository - `<https://github.com/hat-open/hat-core.git>`_

.. warning::

    This project is currently in state of active development. Features,
    functionality and API are unstable.


About
-----

Implementation of PEG parser as described in paper "Parsing Expression
Grammars: A Recognition-Based Syntactic Foundation" (Bryan Ford, 2004).
PEG's grammar itself can be defined by PEG grammar::

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

Example usage of PEG parser::

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
