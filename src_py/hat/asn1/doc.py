import typing

from hat.asn1 import common


def generate_html(refs: typing.Dict[common.TypeRef, common.Type]
                  ) -> str:
    """Generate HTML documentation"""
    modules = {}
    for ref, t in refs.items():
        if ref.module not in modules:
            modules[ref.module] = {}
        modules[ref.module][ref] = t

    toc = ''.join(f'<p>{_generate_module_toc(module_name, module_refs)}</p>'
                  for module_name, module_refs in modules.items())

    content = ''.join(f'<p>{_generate_module(module_name, module_refs)}</p>'
                      for module_name, module_refs in modules.items())

    return (f'<html><head><style>{_style}</style></head><body>'
            f'<div class="toc">{toc}</div>'
            f'<div>{content}</div></body></html>')


_style = """
    body {
        font-family: Arial;
        margin-left: 410px;
    }
    table {
        border: 1px solid black;
        border-spacing: 0px;
    }
    td {
        border: 1px solid black;
        padding: 2px;
    }
    th {
        background-color: #F0F0F0;
        padding: 2px;
        border: 1px solid black;
    }
    .toc {
        position: absolute;
        width: 400px;
        top: 5px;
        left: 5px;
    }
"""


_optional = ' <span style="color: red">&#9773;</span>'


def _generate_module_toc(module_name, refs):
    content = ''.join(f'<li><a href="{_ref_to_href(i)}">{i.name}</a></li>'
                      for i in refs.keys())
    return f'<h3>{module_name} ({len(refs)})</h3><ul>{content}</ul>'


def _generate_module(module_name, refs):
    content = ''.join(f'<tr id="{_ref_to_id(ref)}"><td>{ref.name}</td>'
                      f'<td>{_generate_type(t)}</td></tr>'
                      for ref, t in refs.items())
    return f'<h1>{module_name}</h1><table>{content}</table>'


def _generate_type(t):
    if isinstance(t, common.TypeRef):
        link = f'<a href="{_ref_to_href(t)}">{t.name}</a>'
        return f'<table><tr><th>{link}</th></tr></table>'

    if isinstance(t, common.BooleanType):
        return '<table><tr><th>BOOLEAN</th></tr></table>'

    if isinstance(t, common.IntegerType):
        return '<table><tr><th>INTEGER</th></tr></table>'

    if isinstance(t, common.BitStringType):
        return '<table><tr><th>BIT STRING</th></tr></table>'

    if isinstance(t, common.OctetStringType):
        return '<table><tr><th>OCTET STRING</th></tr></table>'

    if isinstance(t, common.NullType):
        return '<table><tr><th>NULL</th></tr></table>'

    if isinstance(t, common.ObjectIdentifierType):
        return '<table><tr><th>OBJECT IDENTIFIER</th></tr></table>'

    if isinstance(t, common.StringType):
        return f'<table><tr><th>STRING ({t.name})</th></tr></table>'

    if isinstance(t, common.ExternalType):
        return '<table><tr><th>EXTERNAL</th></tr></table>'

    if isinstance(t, common.RealType):
        return '<table><tr><th>REAL</th></tr></table>'

    if isinstance(t, common.EnumeratedType):
        return '<table><tr><th>ENUMERATED</th></tr></table>'

    if isinstance(t, common.EmbeddedPDVType):
        return '<table><tr><th>EMBEDDED PDV</th></tr></table>'

    if isinstance(t, common.ChoiceType):
        content = ''.join(
            f'<tr><td>{i.name}</td><td>{_generate_type(i.type)}</td></tr>'
            for i in t.choices)
        return (f'<table><tr><th colspan="2">CHOICE</th></tr>'
                f'{content}</table>')

    if isinstance(t, common.SetType) or isinstance(t, common.SequenceType):
        title = 'SET' if isinstance(t, common.SetType) else 'SEQUENCE'
        content = ''.join(
            f'<tr><td>{i.name}{_optional if i.optional else ""}</td>'
            f'<td>{_generate_type(i.type)}</td></tr>'
            for i in t.elements)
        return (f'<table><tr><th colspan="2">{title}</th></tr>'
                f'{content}</table>')

    if isinstance(t, common.SetOfType) or isinstance(t, common.SequenceOfType):
        title = 'SET OF' if isinstance(t, common.SetType) else 'SEQUENCE OF'
        content = _generate_type(t.type)
        return (f'<table><tr><th colspan="2">SET OF</th></tr>'
                f'<tr><td>{content}</td></tr></table>')

    if isinstance(t, common.EntityType):
        return '<table><tr><th>ENTITY</th></tr></table>'

    if isinstance(t, common.UnsupportedType):
        return '<table><tr><th>UNSUPPORTED</th></tr></table>'

    if isinstance(t, common.PrefixedType):
        return _generate_type(t.type)

    raise ValueError()


def _ref_to_href(ref):
    return '#' + _ref_to_id(ref)


def _ref_to_id(ref):
    return f'{ref.module}__{ref.name}'
