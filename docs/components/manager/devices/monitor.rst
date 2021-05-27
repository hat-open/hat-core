Monitor server device
=====================

This device provides administration interface for monitoring/controlling
Hat Monitor server.


Back-end/front-end communication
--------------------------------

Back-end device state definition:

.. code:: yaml

    type: object
    required:
        - address
        - mid
        - local_components
        - global_components
    properties:
        address:
            type: string
            description: |
                monitor admin interface
            default: 'ws://127.0.0.1:23022/ws'
        mid:
            type: integer
            decription: |
                monitor server identifier
        local_components:
            type: array
            items:
                type: object
                required:
                    - cid
                    - name
                    - group
                    - address
                    - rank
                properties:
                    cid:
                        type: integer
                    name:
                        type:
                            - string
                            - "null"
                    group:
                        type:
                            - string
                            - "null"
                    address:
                        type:
                            - string
                            - "null"
                    rank:
                        type: integer
        global_components:
            type: array
            items:
                type: object
                required:
                    - cid
                    - mid
                    - name
                    - group
                    - address
                    - rank
                    - blessing
                    - ready
                properties:
                    cid:
                        type: integer
                    mid:
                        type: integer
                    name:
                        type:
                            - string
                            - "null"
                    group:
                        type:
                            - string
                            - "null"
                    address:
                        type:
                            - string
                            - "null"
                    rank:
                        type: integer
                    blessing:
                        type:
                            - integer
                            - "null"
                    ready:
                        type:
                            - integer
                            - "null"

Available RPC actions:

    * ``set_address(address: str) -> None``

        change monitor server address

    * ``set_rank(cid: int, rank: int) -> None``

        change component rank
