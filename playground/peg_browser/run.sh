#!/bin/bash

PYTHONPATH=../../src_py python -m hat.peg_browser \
    --remote-debugging-port=5905 \
    --ui-path ../../build/jshat/peg_browser \
    --fonts-path ../../fonts \
    $*
