#!/bin/sh

. ./env.sh

exec $PYTHON - "$@" << EOF
import pathlib
import sys
import hat.asn1

repo = hat.asn1.Repository(*(pathlib.Path(i) for i in sys.argv[1:]))
print(repo.generate_html_doc())
EOF
