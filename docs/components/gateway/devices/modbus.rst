Modbus devices
==============

According to :ref:`gateway specification <gateway>`, all modbus device event
types have prefix::

    'gateway', <gateway_name>, 'modbus_master', <device_name>, <source>, ...

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
polling `interval` defined for each data in `READ` direction) and reports
any changes as read responses. Also, received write requests are propagated to
remote devices which result in write responses. If connection is lost or could
not be established, device repeatedly tries to establish new connection after
`connect_delay` seconds defined in configuration.

Together with read and write processing, device continuously reports current
status of communication connection and each modbus device identified by
`device_id` data parameter. Status of modbus device identified by `device_id`
is calculated according to availability of all data associated with that
`device_id`: in case all data of a `device_id` are not available, that devices
is considered as `DISCONNECTED`.

To enable communication between modbus master device and rest of the hat
system, following event types are used:

    * 'gateway', <gateway_name>, 'modbus_master', <device_name>, 'gateway', ...

        * ..., 'status'

            Connection status a modbus master device.

            Payload is defined by schema::

                enum:
                    - DISCONNECTED
                    - CONNECTING
                    - CONNECTED

        * ..., 'remote_status', <device_id>

            Status of a remote modbus device, where `<device_id>` is
            remote modbus device identifier `device_id` defined in
            configuration for each data.

            Payload is defined by schema::

                enum:
                    - DISCONNECTED
                    - CONNECTED


        * ..., 'read', <data_name>

            Read response reporting current data value. Data value and cause
            of event reporting are available only in case of successful read.
            `<data_name>` is configuration defined `name` for each data.

            First successful read of data value will be reported with
            `INTERROGATE` `cause` and `result` `SUCCESS`, while all the
            following successful reads, where value is different from previous
            are reported with `CHANGE` cause.
            If read is not successful, `result` equals to any other string
            that indicate reason of failure (`value` and `cause` properties
            are not included). After value is invalidated, next successful
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

            .. note:: if data is not received within `request_timeout`
              after polling, `read` event with result `TIMEOUT` is registered.

        * ..., 'write', <data_name>

            Write response reporting resulting success value. Together with
            `result` that contains success value, this event contains the same
            `request_id` as provided in associated write request event.

            Payload is defined by schema::

                type: object
                required:
                    - request_id
                    - result
                properties:
                    request_id: {}
                    result:
                        enum:
                            - SUCCESS
                            - INVALID_FUNCTION_CODE
                            - INVALID_DATA_ADDRESS
                            - INVALID_DATA_VALUE
                            - FUNCTION_ERROR
                            - TIMEOUT
                            - ENCODE_ERROR

            .. note:: in case response did not arrive within configuration
              defined `request_timeout`, response with `result` `TIMEOUT`
              is registered.

    * 'gateway', <gateway_name>, 'modbus_master', <device_name>, 'system', ...

        * ..., 'write', <data_name>

            Write request containing data value and session identifier used
            for pairing of request/response messages.

            Payload is defined by schema::

                type: object
                required:
                    - request_id
                    - value
                properties:
                    request_id: {}
                    value: {}

.. todo::

    * add status GI - when is this state active in case of connection status
      or in case of device_id?

    * is device_id status CONNECTED when any of data points is available or if
      all or if all data points are available?

    * add [..., 'system', 'status', <device_id>] event to enable/disable
      device polling?

    * do we need [..., 'system', 'write', <data_name>] explicit read request?
