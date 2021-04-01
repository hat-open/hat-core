#!/bin/sh

. ./env.sh

LOG_LEVEL=DEBUG
CONF_PATH=$DATA_PATH/event.yaml

cat > $CONF_PATH << EOF
type: event
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
        hat.event:
            level: $LOG_LEVEL
    root:
        level: INFO
        handlers: ['console_handler']
    disable_existing_loggers: false
monitor:
    name: event
    group: event
    monitor_address: "tcp+sbs://127.0.0.1:23010"
    component_address: "tcp+sbs://127.0.0.1:23012"
backend_engine:
    server_id: 1
    backend:
        module: hat.event.server.backends.dummy
module_engine:
    modules: []
communication:
    address: "tcp+sbs://localhost:23012"
EOF

exec $PYTHON -m hat.event.server \
    --conf $CONF_PATH \
    "$@"
