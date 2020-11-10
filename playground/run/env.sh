#!/bin/sh

RUN_PATH=$(cd $(dirname -- "$0") && pwd)
CORE_PATH=$RUN_PATH/../..
SCHEMAS_JSON_PATH=$CORE_PATH/schemas_json
JSHAT_APP_PATH=$CORE_PATH/build/jshat/app
DATA_PATH=$RUN_PATH/data

export PYTHONPATH=$CORE_PATH/src_py

mkdir -p $DATA_PATH
