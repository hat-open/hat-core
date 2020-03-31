"""Sphinx patches"""

import asyncio
import itertools
import sphinx.addnodes


def setup(app):
    app.setup_extension('sphinx.ext.autodoc')
    app.connect('autodoc-process-docstring', _autodoc_process_docstring)
    return {'version': '0.1'}


def _autodoc_process_docstring(app, what, name, obj, options, lines):
    if what in ("function", "method") and asyncio.iscoroutinefunction(obj):
        lines.insert(0, "**COROUTINE**")


def _pending_xref__find_modname(node):
    if node.parent is None:
        return
    for i in reversed(list(itertools.takewhile(
            lambda x: x != node, node.parent))):
        if i.tagname != 'index':
            continue
        try:
            entries = i.attributes['entries'][0]
            if entries[0] == 'single' and entries[1].endswith(' (module)'):
                return entries[1].split(' ')[0]
        except Exception:
            pass
    return _pending_xref__find_modname(node.parent)


def _pending_xref__get(self, key, failobj=None):
    result = super(type(self), self).get(key, failobj)
    if result is None and key == 'py:module':
        return _pending_xref__find_modname(self)
    return result


sphinx.addnodes.pending_xref.get = _pending_xref__get
