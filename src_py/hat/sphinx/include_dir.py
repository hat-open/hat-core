"""Sphinx extension for for automatic include of all files in directory"""

from docutils import nodes
import docutils.parsers.rst
import pathlib


def setup(app):
    app.add_directive('include_dir', IncludeDirDirective)
    return {'version': '0.1'}


class IncludeDirDirective(docutils.parsers.rst.Directive):

    required_arguments = 1

    def run(self):
        container = nodes.definition_list()
        env = self.state.document.settings.env
        root = pathlib.Path(env.relfn2path(self.arguments[0])[1])
        for file_path in root.glob('**/*'):
            if file_path.is_dir():
                continue
            with open(str(file_path), encoding='utf-8', errors='ignore') as f:
                data = f.read()
            container += nodes.definition_list_item()
            container[-1] += nodes.term(
                text=str(file_path)[len(str(root))+1:])
            container[-1] += nodes.definition()
            container[-1][-1] += nodes.literal_block(text=data)
        return [container]
