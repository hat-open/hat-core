"""Sphinx extension for python code execution

Author:
    alex.forencich
    `http://stackoverflow.com/questions/7250659/python-code-to-generate-part-of-sphinx-documentation-is-it-possible`

"""

from docutils import nodes, statemachine
import docutils.parsers.rst
import io
import os.path
import sys


def setup(app):
    app.add_directive('exec', ExecDirective)


class ExecDirective(docutils.parsers.rst.Directive):
    """Execute the specified python code and insert the output"""

    has_content = True
    option_spec = {'literal': str}

    def run(self):
        oldStdout, sys.stdout = sys.stdout, io.StringIO()

        tab_width = self.options.get(
            'tab-width', self.state.document.settings.tab_width)
        source = self.state_machine.input_lines.source(
            self.lineno - self.state_machine.input_offset - 1)

        try:
            exec('\n'.join(self.content))
            text = sys.stdout.getvalue()
            if 'literal' in self.options:
                return [nodes.literal_block(text=text)]
            else:
                lines = statemachine.string2lines(
                    text, tab_width, convert_whitespace=True)
            self.state_machine.insert_input(lines, source)
            return []
        except Exception:
            return [nodes.error(
                None,
                nodes.paragraph(text=(
                    "Unable to execute python code at %s:%d:" %
                    (os.path.basename(source), self.lineno))),
                nodes.paragraph(text=str(sys.exc_info()[1])))]
        finally:
            sys.stdout = oldStdout
