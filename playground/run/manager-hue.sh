#!/bin/sh

. ./env.sh

exec $PYTHON -m hat.manager.hue \
    --ui-path $JSHAT_APP_PATH/manager-hue \
    "$@"
