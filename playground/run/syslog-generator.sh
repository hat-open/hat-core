#!/bin/sh

. ./env.sh

$PYTHON -m hat.syslog.generator \
    "$@"
