from pathlib import Path

import docutils.statemachine
import docutils.parsers.rst

from hat import stc


def setup(app):
    app.add_directive('scxml', ScxmlDirective)


class ScxmlDirective(docutils.parsers.rst.Directive):

    required_arguments = 1

    def run(self):
        env = self.state.document.settings.env
        source = self.state_machine.input_lines.source(
            self.lineno - self.state_machine.input_offset - 1)
        path = Path(env.relfn2path(self.arguments[0])[1])
        states = stc.parse_scxml(path)
        dot = stc.create_dot_graph(states)
        text = ('.. graphviz::\n\n' +
                '\n'.join('   ' + i for i in dot.split('\n')))
        lines = docutils.statemachine.string2lines(text)
        self.state_machine.insert_input(lines, source)
        return []
