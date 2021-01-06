#!/bin/sh

. ./env.sh

$PYTHON -m hat.syslog.server \
    --ui-path $JSHAT_APP_PATH/syslog \
    --db-path $DATA_PATH/syslog.db \
    "$@"
