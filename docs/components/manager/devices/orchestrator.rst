Orchestrator device
===================

This device provides administration interface for monitoring/controlling
Hat Orchestrator component.


Back-end/front-end communication
--------------------------------

Back-end device state definition:

.. code:: yaml

    type: object
    required:
        - address
        - components
    properties:
        address:
            type: string
            description: |
                orchestrator admin interface
            default: 'ws://127.0.0.1:23021/ws'
        components:
            type: array
            items:
                type: object
                required:
                    - id
                    - name
                    - delay
                    - revive
                    - status
                properties:
                    id:
                        type: integer
                    name:
                        type: string
                    delay:
                        type: number
                    revive:
                        type: boolean
                    status:
                        enum:
                            - STOPPED
                            - DELAYED
                            - STARTING
                            - RUNNING
                            - STOPPING

Available RPC actions:

    * ``set_address(address: str) -> None``

        change orchestrator address

    * ``start(component_id: int) -> None``

        start component process execution

    * ``stop(component_id: int) -> None``

        stop component process execution

    * ``set_revive(component_id: int, revive: bool) -> None``

        change component revive flag






