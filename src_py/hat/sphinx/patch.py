"""Sphinx patches"""

import asyncio
import sphinx.addnodes
import sphinx.domains.python


def setup(app):
    app.setup_extension('sphinx.ext.autodoc')
    # app.connect('autodoc-process-docstring', _autodoc_process_docstring)
    return {'version': '0.1'}


def _autodoc_process_docstring(app, what, name, obj, options, lines):
    if what in ("function", "method") and asyncio.iscoroutinefunction(obj):
        lines.insert(0, "**COROUTINE**")


def _pending_xref__get(self, key, failobj=None):
    result = super(type(self), self).get(key, failobj)
    if result is None and key == 'py:module':
        node = self
        while node and not node.attributes.get('ids'):
            node = node.parent
        if node:
            prefix = 'module-'
            for i in node.attributes['ids']:
                if i.startswith(prefix):
                    return i[len(prefix):]
    return result


def _PythonDomain__resolve_xref(*args, **kwargs):
    return None


# sphinx.addnodes.pending_xref.get = _pending_xref__get

# TODO: disable reference resolving until "multiple targets" fixed
sphinx.domains.python.PythonDomain.resolve_xref = _PythonDomain__resolve_xref
