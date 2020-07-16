#!/usr/bin/env bash

PYTHONPATH=../../src_py python -m hat.syslog.server \
    --ui-path ../../build/jshat/app/syslog \
    $*
