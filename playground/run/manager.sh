#!/bin/sh

. ./env.sh

CONF_PATH=$DATA_PATH/manager.yaml

exec $PYTHON -m hat.manager \
    --conf $CONF_PATH \
    --ui-path $JSHAT_APP_PATH/manager \
    "$@"
