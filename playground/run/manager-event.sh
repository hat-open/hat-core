#!/bin/sh

. ./env.sh

exec $PYTHON -m hat.manager.event \
    --ui-path $JSHAT_APP_PATH/manager-event \
    "$@"
