from hat.sbs import parser
from hat.sbs import serializer


def evaluate_modules(modules):
    """Evaluate modules.

    Args:
        modules (Iterable[parser.AstModule]): modules

    Returns:
        Dict[serializer.Ref,serializer.Type]

    """
    refs = dict(_builtin_refs)
    modules_dict = {module.name: module for module in modules}
    for module in modules_dict.values():
        for ast_type_def in module.type_defs.values():
            if ast_type_def.args:
                continue
            ref = serializer.Ref(module.name, ast_type_def.name)
            refs[ref] = _resolve_ref(modules_dict, ref, [])
    return refs


def _resolve_ref(modules_dict, ref, args):
    if ref in _builtin_arg_refs:
        ast_type_def = _builtin_arg_refs[ref]
    else:
        ast_type_def = modules_dict[ref.module].type_defs[ref.name]

    if len(args) != len(ast_type_def.args):
        raise Exception("number of arguments doesn't match type definition")

    mappings = dict(zip((serializer.Ref(None, arg)
                         for arg in ast_type_def.args),
                        args))
    return _resolve_type(modules_dict, ref.module, ast_type_def.type, mappings)


def _resolve_type(modules_dict, module, ast_type, mappings):
    ref = serializer.Ref(ast_type.module, ast_type.name)
    args = [_resolve_type(modules_dict, module, arg, mappings)
            for arg in ast_type.args]
    entries = [(entry.name,
                _resolve_type(modules_dict, module, entry.type, mappings))
               for entry in ast_type.entries]

    if ref in mappings:
        if args:
            raise Exception("supstituted types dont support arguments")
        return mappings[ref]

    if ref in _builtin_refs:
        if args:
            raise Exception("simple builtin types dont have arguments")
        return ref

    if ref in _builtin_arg_refs:
        return _resolve_ref(modules_dict, ref, args)

    if ref == serializer.Ref(None, 'Array'):
        if len(args) != 1:
            raise Exception('Array requires one argument')
        return serializer.ArrayType(args[0])

    if ref == serializer.Ref(None, 'Tuple'):
        return serializer.TupleType(entries)

    if ref == serializer.Ref(None, 'Union'):
        return serializer.UnionType(entries)

    if not ref.module:
        ref = ref._replace(module=module)

    if not args:
        return ref

    return _resolve_ref(modules_dict, ref, args)


_builtin_refs = {serializer.Ref(None, 'Boolean'): serializer.Boolean,
                 serializer.Ref(None, 'Integer'): serializer.Integer,
                 serializer.Ref(None, 'Float'): serializer.Float,
                 serializer.Ref(None, 'String'): serializer.String,
                 serializer.Ref(None, 'Bytes'): serializer.Bytes,
                 serializer.Ref(None, 'None'): serializer.TupleType([])}


_builtin_arg_refs = {
    serializer.Ref(None, 'Maybe'): parser.AstTypeDef(
        name='Maybe',
        args=['a'],
        type=parser.AstType(
            module=None,
            name='Union',
            entries=[
                parser.AstEntry(
                    name='Nothing',
                    type=parser.AstType(
                        module=None,
                        name='Tuple',
                        entries=[],
                        args=[])),
                parser.AstEntry(
                    name='Just',
                    type=parser.AstType(
                        module=None,
                        name='a',
                        entries=[],
                        args=[]))],
            args=[]))
}
