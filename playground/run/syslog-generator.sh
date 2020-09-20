#!/bin/sh

. ./env.sh

python -m hat.syslog.generator \
    $*
