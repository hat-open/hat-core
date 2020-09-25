#!/bin/sh

. ./env.sh

python -m hat.event.viewer \
    --ui-path $JSHAT_APP_PATH/event-viewer \
    $*
