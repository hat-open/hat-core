r"""PEG Parser

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

"""

import typing

from hat import util


class Node(typing.NamedTuple):
    """Abstract syntax tree node.

    Node names are identifiers of parser's definitions and values
    are other nodes or string values representing matched `Literal`, `Class`
    or `Dot` leafs.

    """
    name: str
    value: typing.List[typing.Union['Node', str]]


Action = typing.Callable[[Node, typing.List], typing.Any]
"""Action"""
util.register_type_alias('Action')


def walk_ast(node: Node,
             actions: typing.Dict[str, Action],
             default_action: typing.Optional[Action] = None
             ) -> typing.Any:
    """Simple depth-first abstract syntax tree parser.

    Actions are key value pairs where keys represent node names and values
    are callables that should be called for appropriate node. Each callable
    receives matched node and list of results from recursively applying
    this function on child nodes. For nodes which name doesn't match any
    action, default action is used. If default action is not defined and node
    name doesn't match action, result is None and recursion is stopped.

    """
    action = actions.get(node.name, default_action)
    if not action:
        return
    children = [walk_ast(i, actions, default_action)
                if isinstance(i, Node) else i
                for i in node.value]
    return action(node, children)


class Sequence(typing.NamedTuple):
    expressions: typing.List['Expression']


class Choice(typing.NamedTuple):
    expressions: typing.List['Expression']


class Not(typing.NamedTuple):
    expression: 'Expression'


class And(typing.NamedTuple):
    expression: 'Expression'


class OneOrMore(typing.NamedTuple):
    expression: 'Expression'


class ZeroOrMore(typing.NamedTuple):
    expression: 'Expression'


class Optional(typing.NamedTuple):
    expression: 'Expression'


class Identifier(typing.NamedTuple):
    value: str


class Literal(typing.NamedTuple):
    value: str


class Class(typing.NamedTuple):
    values: typing.List[typing.Union[str, typing.Tuple[str, str]]]


class Dot(typing.NamedTuple):
    pass


Expression = typing.Union[Sequence, Choice, Not, And, OneOrMore, ZeroOrMore,
                          Optional, Identifier, Literal, Class, Dot]
"""Expression"""
util.register_type_alias('Expression')


class MatchResult(typing.NamedTuple):
    """Match result

    Args:
        node: matched node or ``None`` if match failed
        rest: remaining input data

    """
    node: typing.Optional[Node]
    rest: str


class MatchCallFrame(typing.NamedTuple):
    """Match call frame

    Args:
        name: definition name
        data: input data

    """
    name: str
    data: str


MatchCallStack = typing.Iterable[MatchCallFrame]
"""Match call stack"""
util.register_type_alias('MatchCallStack')


DebugCb = typing.Callable[[MatchResult, MatchCallStack], None]
"""Debug callback"""
util.register_type_alias('DebugCb')


class Grammar:
    """PEG Grammar.

    Args:
        definitions: grammar definitions
        starting: starting definition name

    """

    def __init__(self,
                 definitions: typing.Union[str,
                                           typing.Dict[str, Expression]],
                 starting: str):
        if isinstance(definitions, str):
            ast = _peg_grammar.parse(definitions)
            definitions = walk_ast(ast, _peg_actions)
            definitions = {k: _reduce_expression(v)
                           for k, v in definitions.items()}
        self._definitions = definitions
        self._starting = starting

    @property
    def definitions(self) -> typing.Dict[str, Expression]:
        """Definitions"""
        return self._definitions

    @property
    def starting(self) -> str:
        """Starting definition name"""
        return self._starting

    def parse(self,
              data: str,
              debug_cb: typing.Optional[DebugCb] = None
              ) -> Node:
        """Parse input data.

        `debug_cb` is optional function which can be used for monitoring and
        debugging parse steps. It is called each time named definition
        is successfully or unsuccessfully matched. This function receives
        match result and match call stack.

        """
        state = _State(grammar=self,
                       data=data,
                       call_stack=_MatchCallStack(None, None),
                       debug_cb=debug_cb)
        result = _match(state, self._starting)
        if result.node is None:
            raise Exception("could not match starting definition")
        x = _reduce_node(result.node)
        return x


def console_debug_cb(result: MatchResult, call_stack: MatchCallStack):
    """Simple console debugger."""
    success = '+++' if result.node else '---'
    stack = ', '.join(frame.name for frame in call_stack)
    consumed = util.first(call_stack).data[:-len(result.rest)]
    print(success, stack)
    print('<<<', consumed)
    print('>>>', result.rest, flush=True)


class _MatchCallStack(typing.NamedTuple):
    frame: typing.Optional[MatchCallFrame]
    previous: typing.Optional['_MatchCallStack']

    def __iter__(self):
        current = self
        while current and current.frame:
            yield current.frame
            current = current.previous


class _State(typing.NamedTuple):
    grammar: Grammar
    data: str
    call_stack: _MatchCallStack
    debug_cb: DebugCb


def _match(state, name):
    call_frame = MatchCallFrame(name, state.data)
    if call_frame in state.call_stack:
        raise Exception('Infinite matching recursion detected')
    state = state._replace(
        call_stack=_MatchCallStack(call_frame, state.call_stack))
    result = _match_expression(state, state.grammar.definitions[name])
    if result.node:
        result = result._replace(
            node=result.node._replace(name=name))
    if state.debug_cb:
        debug_result = MatchResult(
            node=(_reduce_node(result.node) if result.node else None),
            rest=result.rest)
        state.debug_cb(debug_result, state.call_stack)
    return result


def _match_expression(state, expression):
    t = type(expression)
    if t == Choice:
        return _match_choice(state, expression)
    if t == Sequence:
        return _match_sequence(state, expression)
    if t == Not:
        return _match_not(state, expression)
    if t == And:
        return _match_and(state, expression)
    if t == OneOrMore:
        return _match_oneormore(state, expression)
    if t == ZeroOrMore:
        return _match_zeroormore(state, expression)
    if t == Optional:
        return _match_optional(state, expression)
    if t == Identifier:
        return _match_identifier(state, expression)
    if t == Literal:
        return _match_literal(state, expression)
    if t == Class:
        return _match_class(state, expression)
    if t == Dot:
        return _match_dot(state, expression)
    raise ValueError('unsupported expression type')


def _match_choice(state, expression):
    for i in expression.expressions:
        result = _match_expression(state, i)
        if result.node:
            return result
    return MatchResult(None, state.data)


def _match_sequence(state, expression):
    nodes = []
    for i in expression.expressions:
        result = _match_expression(state, i)
        if not result.node:
            return MatchResult(None, state.data)
        nodes.append(result.node)
        state = state._replace(data=result.rest)
    return MatchResult(Node(None, nodes), state.data)


def _match_not(state, expression):
    result = _match_expression(state, expression.expression)
    return (MatchResult(None, state.data) if result.node
            else MatchResult(Node(None, []), state.data))


def _match_and(state, expression):
    node = _match_expression(state, expression.expression).node
    return MatchResult(Node(None, []) if node else None, state.data)


def _match_oneormore(state, expression):
    return _match_expression(state, Sequence([
        expression.expression,
        ZeroOrMore(expression.expression)]))


def _match_zeroormore(state, expression):
    nodes = []
    while True:
        result = _match_expression(state, expression.expression)
        if not result.node:
            return MatchResult(Node(None, nodes), state.data)
        nodes.append(result.node)
        state = state._replace(data=result.rest)


def _match_optional(state, expression):
    result = _match_expression(state, expression.expression)
    if result.node:
        return result
    return MatchResult(Node(None, []), state.data)


def _match_identifier(state, expression):
    result = _match(state, expression.value)
    if result.node:
        result = result._replace(node=Node(None, [result.node]))
    return result


def _match_literal(state, expression):
    data = state.data[:len(expression.value)]
    if data != expression.value:
        return MatchResult(None, state.data)
    rest = state.data[len(expression.value):]
    return MatchResult(Node(None, [data]), rest)


def _match_class(state, expression):
    if state.data:
        for i in expression.values:
            if isinstance(i, str):
                matched = state.data[0] == i
            else:
                matched = i[0] <= state.data[0] <= i[1]
            if matched:
                return MatchResult(Node(None, [state.data[:1]]),
                                   state.data[1:])
    return MatchResult(None, state.data)


def _match_dot(state, expression):
    if not state.data:
        return MatchResult(None, state.data)
    return MatchResult(Node(None, [state.data[:1]]), state.data[1:])


def _reduce_expression(expr):
    if hasattr(expr, 'expressions'):
        if len(expr.expressions) == 1:
            return _reduce_expression(expr.expressions[0])
        return expr._replace(expressions=[_reduce_expression(i)
                                          for i in expr.expressions])
    if hasattr(expr, 'expression'):
        return expr._replace(expression=_reduce_expression(expr.expression))
    return expr


def _reduce_node(node):
    return node._replace(value=list(_reduce_node_list(node.value)))


def _reduce_node_list(nodes):
    for node in nodes:
        if not isinstance(node, Node):
            yield node
        elif node.name is None:
            yield from _reduce_node_list(node.value)
        else:
            yield _reduce_node(node)


_peg_grammar = Grammar({
    'Grammar': Sequence([
        Identifier('Spacing'),
        OneOrMore(Identifier('Definition')),
        Identifier('EndOfFile')]),
    'Definition': Sequence([
        Identifier('Identifier'),
        Identifier('LEFTARROW'),
        Identifier('Expression')]),
    'Expression': Sequence([
        Identifier('Sequence'),
        ZeroOrMore(Sequence([
            Identifier('SLASH'),
            Identifier('Sequence')]))]),
    'Sequence': ZeroOrMore(Identifier('Prefix')),
    'Prefix': Sequence([
        Optional(Choice([
            Identifier('AND'),
            Identifier('NOT')])),
        Identifier('Suffix')]),
    'Suffix': Sequence([
        Identifier('Primary'),
        Optional(Choice([
            Identifier('QUESTION'),
            Identifier('STAR'),
            Identifier('PLUS')]))]),
    'Primary': Choice([
        Sequence([
            Identifier('Identifier'),
            Not(Identifier('LEFTARROW'))]),
        Sequence([
            Identifier('OPEN'),
            Identifier('Expression'),
            Identifier('CLOSE')]),
        Identifier('Literal'),
        Identifier('Class'),
        Identifier('DOT')]),
    'Identifier': Sequence([
        Identifier('IdentStart'),
        ZeroOrMore(Identifier('IdentCont')),
        Identifier('Spacing')]),
    'IdentStart': Class([('a', 'z'),
                         ('A', 'Z'),
                         '_']),
    'IdentCont': Choice([
        Identifier('IdentStart'),
        Class([('0', '9')])]),
    'Literal': Choice([
        Sequence([
            Class(["'"]),
            ZeroOrMore(Sequence([
                Not(Class(["'"])),
                Identifier('Char')])),
            Class(["'"]),
            Identifier('Spacing')]),
        Sequence([
            Class(['"']),
            ZeroOrMore(Sequence([
                Not(Class(['"'])),
                Identifier('Char')])),
            Class(['"']),
            Identifier('Spacing')])]),
    'Class': Sequence([
        Literal('['),
        ZeroOrMore(Sequence([
            Not(Literal(']')),
            Identifier('Range')])),
        Literal(']'),
        Identifier('Spacing')]),
    'Range': Choice([
        Sequence([
            Identifier('Char'),
            Literal('-'),
            Identifier('Char')]),
        Identifier('Char')]),
    'Char': Choice([
        Sequence([
            Literal('\\'),
            Class(['n', 'r', 't', "'", '"', '[', ']', '\\'])]),
        Sequence([
            Literal('\\'),
            Literal('x'),
            Identifier('Hex'),
            Identifier('Hex')]),
        Sequence([
            Literal('\\'),
            Literal('u'),
            Identifier('Hex'),
            Identifier('Hex'),
            Identifier('Hex'),
            Identifier('Hex')]),
        Sequence([
            Not(Literal('\\')),
            Dot()])]),
    'Hex': Class([('0', '9'),
                  ('a', 'f'),
                  ('A', 'F')]),
    'LEFTARROW': Sequence([
        Literal('<-'),
        Identifier('Spacing')]),
    'SLASH': Sequence([
        Literal('/'),
        Identifier('Spacing')]),
    'AND': Sequence([
        Literal('&'),
        Identifier('Spacing')]),
    'NOT': Sequence([
        Literal('!'),
        Identifier('Spacing')]),
    'QUESTION': Sequence([
        Literal('?'),
        Identifier('Spacing')]),
    'STAR': Sequence([
        Literal('*'),
        Identifier('Spacing')]),
    'PLUS': Sequence([
        Literal('+'),
        Identifier('Spacing')]),
    'OPEN': Sequence([
        Literal('('),
        Identifier('Spacing')]),
    'CLOSE': Sequence([
        Literal(')'),
        Identifier('Spacing')]),
    'DOT': Sequence([
        Literal('.'),
        Identifier('Spacing')]),
    'Spacing': ZeroOrMore(Choice([
        Identifier('Space'),
        Identifier('Comment')])),
    'Comment': Sequence([
        Literal('#'),
        ZeroOrMore(Sequence([
            Not(Identifier('EndOfLine')),
            Dot()])),
        Identifier('EndOfLine')]),
    'Space': Choice([
        Literal(' '),
        Literal('\t'),
        Identifier('EndOfLine')]),
    'EndOfLine': Choice([
        Literal('\r\n'),
        Literal('\n'),
        Literal('\r')]),
    'EndOfFile': Not(Dot())
}, 'Grammar')


_peg_actions = {
    'Grammar': lambda n, c: {k: v for k, v in filter(bool, c)},
    'Definition': lambda n, c: (c[0].value, c[2]),
    'Expression': lambda n, c: Choice(list(c[::2])),
    'Sequence': lambda n, c: Sequence(c),
    'Prefix': lambda n, c: (c[0] if len(c) == 1 else
                            c[0](c[1])),
    'Suffix': lambda n, c: (c[0] if len(c) == 1 else
                            c[1](c[0])),
    'Primary': lambda n, c: (c[1] if c[0] is None else
                             c[0]),
    'Identifier': lambda n, c: Identifier(''.join(c[:-1])),
    'IdentStart': lambda n, c: c[0],
    'IdentCont': lambda n, c: c[0],
    'Literal': lambda n, c: Literal(''.join(c[1:-2])),
    'Class': lambda n, c: Class(c[1:-2]),
    'Range': lambda n, c: (c[0] if len(c) == 1 else
                           (c[0], c[2])),
    'Char': lambda n, c: (c[0] if c[0] != '\\' else
                          '\n' if c[1] == 'n' else
                          '\r' if c[1] == 'r' else
                          '\t' if c[1] == 't' else
                          "'" if c[1] == "'" else
                          '"' if c[1] == '"' else
                          '[' if c[1] == '[' else
                          ']' if c[1] == ']' else
                          '\\' if c[1] == '\\' else
                          chr(int(c[2:], 16))),
    'Hex': lambda n, c: c[0],
    'AND': lambda n, c: And,
    'NOT': lambda n, c: Not,
    'QUESTION': lambda n, c: Optional,
    'STAR': lambda n, c: ZeroOrMore,
    'PLUS': lambda n, c: OneOrMore,
    'DOT': lambda n, c: Dot()
}
