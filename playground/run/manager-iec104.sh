#!/bin/sh

. ./env.sh

exec $PYTHON -m hat.manager.iec104 \
    --ui-path $JSHAT_APP_PATH/manager-iec104 \
    "$@"
