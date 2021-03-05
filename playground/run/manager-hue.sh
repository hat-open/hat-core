#!/bin/sh

. ./env.sh

$PYTHON -m hat.manager.hue \
    --ui-path $JSHAT_APP_PATH/manager-hue \
    "$@"
