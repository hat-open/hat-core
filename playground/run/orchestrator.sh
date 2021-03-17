#!/bin/sh

. ./env.sh

LOG_LEVEL=DEBUG
CONF_PATH=$DATA_PATH/orchestrator.yaml

cat > $CONF_PATH << EOF
type: orchestrator
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
components:
  - name: test
    args:
        - sh
        - "-c"
        - "sleep 5 && echo test"
    delay: 0
    revive: true
ui:
    address: "http://127.0.0.1:23021"
EOF

exec $PYTHON -m hat.orchestrator \
    --ui-path $JSHAT_APP_PATH/orchestrator \
    --conf $CONF_PATH \
    "$@"
