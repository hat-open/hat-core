Event server device
===================

This device provides administration interface for monitoring/controlling
Hat Event server.


Event registration DSL
----------------------

.. todo::

    ...


Back-end/front-end communication
--------------------------------

Back-end device state definition:

.. code:: yaml

    type: object
    required:
        - address
        - latest
        - changes
    properties:
        address:
            type: string
            default: 'tcp+sbs://127.0.0.1:23012'
        latest:
            type: array
            items:
                "$ref": "#/definitions/event"
        changes:
            type: array
            items:
                "$ref": "#/definitions/event"
    definitions:
        event:
            type: object
            required:
                - event_id
                - event_type
                - timestamp
                - source_timestamp
                - payload
            properties:
                event_id:
                    type: object
                    required:
                        - server
                        - instance
                    properties:
                        server:
                            type: integer
                        instance:
                            type: integer
                event_type:
                    type: array
                    items:
                        type: string
                timestamp:
                    type: number
                source_timestamp:
                    type:
                        - number
                        - "null"
                payload: {}

Available RPC actions:

    * ``set_address(address: str) -> None``

        change event server address

    * ``register(text: str, with_source_timestamp: bool) -> None``

        register events
