#!/bin/sh

. ./env.sh

cd $CORE_PATH
doit schemas pymod jshat_app jshat_view
