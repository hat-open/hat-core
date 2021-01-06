#!/bin/sh

. ./env.sh

$PYTHON -m hat.event.viewer \
    --ui-path $JSHAT_APP_PATH/event-viewer \
    "$@"
