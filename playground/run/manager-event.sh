#!/bin/sh

. ./env.sh

$PYTHON -m hat.manager.event \
    --ui-path $JSHAT_APP_PATH/manager-event \
    "$@"
