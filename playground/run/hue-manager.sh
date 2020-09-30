#!/bin/sh

. ./env.sh

python -m hat.drivers.hue.manager \
    --ui-path $JSHAT_APP_PATH/hue-manager \
    $*
