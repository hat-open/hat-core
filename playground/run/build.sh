#!/bin/sh

. ./env.sh

cd $CORE_PATH
exec $PYTHON -m doit schemas pymod jshat_app jshat_view
