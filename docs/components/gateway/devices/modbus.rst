Modbus devices
==============

According to :ref:`gateway specification <gateway>`, all modbus device event
types have prefix::

    'gateway', <gateway_name>, <device_type>, <device_name>, <source>, ...

Together with modbus specific events, generic `enable` and `running` events
are also supported.

Modbus specific events don't contain `source_timestamp`.

Modbus device configurations are defined by schema:

.. literalinclude:: ../../../../schemas_json/gateway/modbus.yaml
    :language: yaml


Data value
----------

.. todo::

    explain encoding/decoding of data values based on modbus registers


Modbus master
-------------

Once enabled, modbus master device will try to open communication connection
defined by configuration parameters. While connection is established,
this device repeatedly reads modbus registers (in accordance to configured
polling interval) and reports any changes as read responses. Also, received
write requests are propagated to remote devices which result in write
responses. If connection is lost or could not be established, device repeatedly
tries to establish new connection.

Together with read and write processing, device continuously reports current
status of communication connection and each modbus device identified by
`device_id` data parameter. Status of modbus device identified by `device_id`
is calculated according to availability of all data associated with that
`device_id`.

To enable communication between modbus master device and rest of hat system,
following event types are used:

    * 'gateway', <gateway_name>, <device_type>, <device_name>, 'gateway', ...

        * ..., 'status'[, <device_id>]

            Status of connection (event type without `<device_id>`) or status
            of remote modbus device (event type with `<device_id>`).

            Payload is defined by schema::

                enum:
                    - DISCONNECTED
                    - CONNECTING
                    - CONNECTED

        * ..., 'read', <data_name>

            Read response reporting current data value. Data value and cause
            of event reporting are available only in case of successful read.

            First successful read of data value will be reported with
            `INTERROGATE` cause while all following successful reads where
            value is different from previous are reported with `CHANGE` cause.
            If read is not successful, value is invalidated - next successful
            read will be reported with `INTERROGATED` cause.

            Payload is defined by schema::

                type: object
                required:
                    - result
                properties:
                    result:
                        enum:
                            - SUCCESS
                            - INVALID_FUNCTION_CODE
                            - INVALID_DATA_ADDRESS
                            - INVALID_DATA_VALUE
                            - FUNCTION_ERROR
                            - TIMEOUT
                            - DECODE_ERROR
                    value: {}
                    cause:
                        enum:
                            - INTERROGATE
                            - CHANGE

        * ..., 'write', <data_name>

            Write response reporting resulting success value. Together with
            success value, this event contains same `session_id` as provided
            in associated write request.

            Payload is defined by schema::

                type: object
                required:
                    - session_id
                    - result
                properties:
                    session_id: {}
                    result:
                        enum:
                            - SUCCESS
                            - INVALID_FUNCTION_CODE
                            - INVALID_DATA_ADDRESS
                            - INVALID_DATA_VALUE
                            - FUNCTION_ERROR
                            - TIMEOUT
                            - ENCODE_ERROR

    * 'gateway', <gateway_name>, <device_type>, <device_name>, 'system', ...

        * ..., 'write', <data_name>

            Write request containing data value and session identifier used
            for pairing of request/response messages.

            Payload is defined by schema::

                type: object
                required:
                    - session_id
                    - value
                properties:
                    session_id: {}
                    value: {}

.. todo::

    * add status GI - when is this state active in case of connection status
      or in case of device_id?

    * is device_id status CONNECTED when any of data points is available or if
      all or if all data points are available?

    * add [..., 'system', 'status', <device_id>] event to enable/disable
      device polling?

    * do we need [..., 'system', 'write', <data_name>] explicit read request?
