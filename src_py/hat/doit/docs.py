import enum
import subprocess
import sys

from hat.doit import common


class SphinxOutputType(enum.Enum):
    HTML = 'html'
    LATEX = 'latex'


def sphinx_build(out_type, src, dest):
    common.mkdir_p(dest)
    subprocess.run([sys.executable, '-m', 'sphinx', '-q', '-b', out_type.value,
                    str(src), str(dest)],
                   check=True)


def latex_build(src, dest):
    common.mkdir_p(dest)
    for i in src.glob('*.tex'):
        subprocess.run(['xelatex', '-interaction=batchmode',
                        f'-output-directory={dest.resolve()}', i.name],
                       cwd=src, stdout=subprocess.DEVNULL, check=True)
