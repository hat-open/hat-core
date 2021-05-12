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

All modbus native data types are encoded as 1bit or 16bit addressable values.
Because of different data encoding schemas, single user defined data values
can occupy only parts of modbus registers or span across multiple registers.
To accommodate these different encoding rules, modbus gateway devices represent
single data point values as list of bits, encoded as single unsigned integer,
with size specified by configuration parameters.

Among other parameters, each data specifies:

    * data type (1bit or 16bit register size)
    * bit size
    * starting register address
    * starting register bit (bit offset)

List of bit values is created by iterative reading of register values starting
with `starting register address` and incrementing register address by 1. Bits
in each register are read starting with most significant and advancing to the
least significant bit. Starting register bit defines bit offset - number of
bits which are skipped during start of this iterative procedure. These skipped
bits are not included in resulting value and are not taken into account in
bit size calculation.


Encoding/decoding example
'''''''''''''''''''''''''

In case of 16bit registers with content:

    +---------+--------+
    | Address | Value  |
    +=========+========+
    | 1000    | 0x1234 |
    +---------+--------+
    | 1001    | 0x5678 |
    +---------+--------+
    | 1002    | 0x9abc |
    +---------+--------+

When data item is configured with properties:

    * bit size: 32
    * starting register address: 1000
    * starting register bit: 16

Data value is unlimited unsigned integer 0x3456789a.


Modbus master
-------------

Once enabled, modbus master device will try to open communication connection
defined by configuration parameters. While connection is established,
this device repeatedly reads modbus registers (in accordance to configured
polling `interval` defined for each data in ``READ`` direction) and reports
any changes as read responses. Also, received write requests are propagated to
remote devices which result in write responses. If connection is lost or could
not be established, device repeatedly tries to establish new connection after
`connect_delay` seconds defined in configuration.

Together with read and write processing, device continuously reports current
status of communication connection and each modbus device identified by
`device_id` data parameter. Status of modbus device identified by `device_id`
is calculated according to availability of all data associated with that
`device_id`: in case all data of a `device_id` are not available, that devices
is considered as ``DISCONNECTED``.

Polling of data values can be enabled/disabled based on `device_id`. Initially,
polling for all remote devices is disabled and has to be explicitly enabled.

To enable communication between modbus master device and rest of the hat
system, following event types are used:

    * 'gateway', <gateway_name>, 'modbus_master', <device_name>, 'gateway', ...

        * ..., 'status'

            Connection status of a modbus master device.

            Payload is defined by schema::

                enum:
                    - DISCONNECTED
                    - CONNECTING
                    - CONNECTED

        * ..., 'remote_device', <device_id>, 'status'

            Status of a remote modbus device, where `<device_id>` is
            remote modbus device identifier `device_id` defined in
            configuration for each data.

            Payload is defined by schema::

                enum:
                    - DISCONNECTED
                    - CONNECTED

        * ..., 'remote_device', <device_id>, 'read', <data_name>

            Read response reporting current data value. Data value and cause
            of event reporting are available only in case of successful read.
            `<data_name>` is configuration defined `name` for each data.

            First successful read of data value will be reported with
            ``INTERROGATE`` `cause` and `result` ``SUCCESS``, while all the
            following successful reads, where value is different from previous
            are reported with ``CHANGE`` cause.
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
                    value:
                        type: integer
                    cause:
                        enum:
                            - INTERROGATE
                            - CHANGE

            .. note:: if data is not received within `request_timeout`
              after polling, `read` event with result ``TIMEOUT`` is registered.

        * ..., 'remote_device', <device_id>, 'write', <data_name>

            Write response reporting resulting success value. Together with
            `result` that contains success value, this event contains the same
            `request_id` as provided in associated write request event.

            Payload is defined by schema::

                type: object
                required:
                    - request_id
                    - result
                properties:
                    request_id:
                        type: string
                    result:
                        enum:
                            - SUCCESS
                            - INVALID_FUNCTION_CODE
                            - INVALID_DATA_ADDRESS
                            - INVALID_DATA_VALUE
                            - FUNCTION_ERROR
                            - TIMEOUT

            .. note:: in case response did not arrive within configuration
              defined `request_timeout`, response with `result` ``TIMEOUT``
              is registered.

    * 'gateway', <gateway_name>, 'modbus_master', <device_name>, 'system', ...

        * ..., 'remote_device', <device_id>, 'enable'

            Enable polling of data associated with remote modbus device with
            `<device_id>` identifier.

            Payload is JSON boolean value which is set to ``true`` in case of
            enabling remote device and set to ``false`` in case of disabling
            remote device.

        * ..., 'remote_device', <device_id>, 'write', <data_name>

            Write request containing data value and session identifier used
            for pairing of request/response messages.

            Payload is defined by schema::

                type: object
                required:
                    - request_id
                    - value
                properties:
                    request_id:
                        type: string
                    value:
                        type: integer

.. todo::

    * add status GI - when is this state active in case of connection status
      or in case of device_id?

    * is device_id status CONNECTED when any of data points is available or if
      all or if all data points are available?

    * do we need [..., 'system', 'remote_device', <device_id>, 'read',
      <data_name>] explicit read request?
