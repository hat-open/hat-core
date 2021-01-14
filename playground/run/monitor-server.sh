#!/bin/sh

. ./env.sh

LOG_LEVEL=DEBUG
CONF_PATH=$DATA_PATH/monitor.yaml

cat > $CONF_PATH << EOF
type: monitor
log:
    version: 1
    formatters:
        console_formatter:
            format: "[%(asctime)s %(levelname)s %(name)s] %(message)s"
    handlers:
        console_handler:
            class: logging.StreamHandler
            formatter: console_formatter
            level: DEBUG
    loggers:
        hat.monitor:
            level: $LOG_LEVEL
    root:
        level: INFO
        handlers: ['console_handler']
    disable_existing_loggers: false
server:
    address: "tcp+sbs://127.0.0.1:23010"
    default_rank: 1
master:
    address: "tcp+sbs://127.0.0.1:23011"
    default_algorithm: BLESS_ALL
    group_algorithms: {}
slave:
    parents: []
ui:
    address: "http://127.0.0.1:23022"
EOF

$PYTHON -m hat.monitor.server \
    --ui-path $JSHAT_APP_PATH/monitor \
    --conf $CONF_PATH \
    "$@"
