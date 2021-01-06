#!/bin/sh

. ./env.sh

cd $CORE_PATH
$PYTHON -m doit schemas pymod jshat_app jshat_view
