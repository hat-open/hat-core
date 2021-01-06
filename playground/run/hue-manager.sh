#!/bin/sh

. ./env.sh

$PYTHON -m hat.drivers.hue.manager \
    --ui-path $JSHAT_APP_PATH/hue-manager \
    "$@"
