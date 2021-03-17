#!/bin/sh

. ./env.sh

exec $PYTHON -m hat.syslog.generator \
    "$@"
