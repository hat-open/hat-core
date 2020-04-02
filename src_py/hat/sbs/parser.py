from hat import util
import hat.peg


AstModule = util.namedtuple(
    'AstModule',
    ['name', 'str'],
    ['type_defs', 'Dict[str,AstTypeDef]'])

AstTypeDef = util.namedtuple(
    'AstTypeDef',
    ['name', 'str'],
    ['args', 'List[str]'],
    ['type', 'AstType'])

AstType = util.namedtuple(
    'AstType',
    ['module', 'Optional[str]'],
    ['name', 'str'],
    ['entries', 'List[AstEntry]'],
    ['args', 'List[AstType]'])

AstEntry = util.namedtuple(
    'AstEntry',
    ['name', 'str'],
    ['type', 'AstType'])


def parse(schema):
    """Parse SBS schema

    Args:
        schema (str): SBS schema

    Returns:
        AstModule

    """
    ast = _grammar.parse(schema)
    return hat.peg.walk_ast(ast, _actions)


_grammar = hat.peg.Grammar(r'''
    Module          <- OWS 'module' MWS Identifier TypeDefinitions OWS EOF
    TypeDefinitions <- (MWS TypeDefinition (MWS TypeDefinition)*)?
    TypeDefinition  <- Identifier OWS ArgNames? OWS '=' OWS Type

    Type            <- TSimple
                     / TArray
                     / TTuple
                     / TUnion
                     / TIdentifier
    TSimple         <- 'Boolean'
                     / 'Integer'
                     / 'Float'
                     / 'String'
                     / 'Bytes'
    TArray          <- 'Array' OWS '(' OWS Type OWS ')'
    TTuple          <- 'Tuple' OWS '{' OWS Entries? OWS '}'
    TUnion          <- 'Union' OWS '{' OWS Entries? OWS '}'
    TIdentifier     <- Identifier ('.' Identifier)? (OWS ArgTypes)?

    Entries         <- Entry (MWS Entry)*
    Entry           <- Identifier OWS ':' OWS Type

    ArgNames        <- '(' OWS Identifiers? OWS ')'
    ArgTypes        <- '(' OWS Types? OWS ')'
    Identifiers     <- Identifier (MWS Identifier)*
    Types           <- Type (MWS Type)*

    Identifier      <- [A-Za-z][A-Za-z0-9_]*

    # mandatory white-space
    MWS             <- (WS / Comment)+
    # optional white-space
    OWS             <- (WS / Comment)*

    Comment         <- '#' (!EOL .)* EOL
    WS              <- ',' / ' ' / '\t' / EOL
    EOL             <- '\r\n' / '\n' / '\r'
    EOF             <- !.
''', 'Module')


_actions = {
    'Module': lambda n, c: AstModule(name=c[3],
                                     type_defs=c[4]),
    'TypeDefinitions': lambda n, c: {c[i].name: c[i]
                                     for i in range(1, len(c), 2)},
    'TypeDefinition': lambda n, c: AstTypeDef(name=c[0],
                                              args=c[2] or [],
                                              type=c[-1]),
    'Type': lambda n, c: c[0],
    'TSimple': lambda n, c: AstType(module=None,
                                    name=c[0],
                                    entries=[],
                                    args=[]),
    'TArray': lambda n, c: AstType(module=None,
                                   name='Array',
                                   entries=[],
                                   args=[c[4]]),
    'TTuple': lambda n, c: AstType(module=None,
                                   name='Tuple',
                                   entries=c[4] or [],
                                   args=[]),
    'TUnion': lambda n, c: AstType(module=None,
                                   name='Union',
                                   entries=c[4] or [],
                                   args=[]),
    'TIdentifier': lambda n, c: AstType(module=(c[0]
                                                if len(c) > 1 and c[1] == '.'
                                                else None),
                                        name=(c[2]
                                              if len(c) > 1 and c[1] == '.'
                                              else c[0]),
                                        entries=[],
                                        args=(c[-1] if len(c) > 1 and not c[-2]
                                              else [])),
    'Entries': lambda n, c: [c[i] for i in range(0, len(c), 2)],
    'Entry': lambda n, c: AstEntry(name=c[0],
                                   type=c[-1]),
    'ArgNames': lambda n, c: c[2] or [],
    'ArgTypes': lambda n, c: c[2] or [],
    'Identifiers': lambda n, c: [c[i] for i in range(0, len(c), 2)],
    'Types': lambda n, c: [c[i] for i in range(0, len(c), 2)],
    'Identifier': lambda n, c: ''.join(c)}
