"""Sphinx extension for automatic include of all files in directory"""

from pathlib import Path
import io

import docutils.parsers.rst
import docutils.statemachine


def setup(app):
    app.add_directive('include_dir', IncludeDirDirective)
    return {'version': '0.1'}


class IncludeDirDirective(docutils.parsers.rst.Directive):

    required_arguments = 1

    def run(self):
        env = self.state.document.settings.env
        source = self.state_machine.input_lines.source(
            self.lineno - self.state_machine.input_offset - 1)

        root_rel = Path(self.arguments[0])
        root_abs = Path(env.relfn2path(self.arguments[0])[1])
        text = io.StringIO()

        for path in root_abs.glob('**/*'):
            if path.is_dir():
                continue
            path = path.relative_to(root_abs)
            text.write(
                f'.. literalinclude:: {root_rel / path}\n'
                f'   :caption: :download:`{path} <{root_rel / path}>`\n\n')

        lines = docutils.statemachine.string2lines(text.getvalue())
        self.state_machine.insert_input(lines, source)
        return []
