#!/bin/sh

set -e

cd $(dirname -- "$0")

PYTHONPATH=../../src_py python << EOF
from pathlib import Path
from hat import stc

states = stc.parse_scxml(Path('command.scxml'))
with open('command.dot', 'w') as f:
    f.write(stc.create_dot_graph(states))
EOF

dot -Tsvg -o command.svg command.dot $*
