.. _manager:

Manager
=======

Manager is administration tool which enables communication with remote devices
and components. It can be used for testing various communication
protocols/equipment and monitoring/controlling other Hat components.
Usage of this tool is aimed at system administrators responsible for
maintaining Hat systems and configuring communication with 3rd party devices.


Running
-------

By installing Manager from `hat-manager` package, executable `hat-manager`
becomes available and can be used for starting this component.

    .. program-output:: python -m hat.manager --help

If configuration could not be found, Manager is started with default
configuration and front-end available at ``http://127.0.0.1:23024``.

All configuration parameters can be modified through front-end GUI.


Overview
--------

.. drawio-image:: manager.drawio
   :page-index: 0
   :align: center

Manager is implemented as server application with web-based front-end GUI.
Back-end implements most of communication functionalities while front-end
provides thin layer responsible only for data visualization and user
interaction. All front-ends share and operate on single back-end state.

Communication between back-end and front-end is based on :ref:`juggler` with
addition of RPC messages. Front-end can request execution of RPC actions
while back-end continuously updates and shares it's state as juggler's state
data.

Back-end's configuration parameters can be modified during Manager execution
and persisted as configuration file.


Devices
-------

Manager devices provide modular encapsulation of functionality associated with
specific communication protocols.

Each manager device implementation includes:

    * configuration

        Device specific configuration parameters which enable reconstruction
        of device state between manager executions.

    * state data

        Dynamically changed JSON serializable data representing device state
        which should be visible on front-end GUI.

    * actions

        RPC actions available for front-end mapping of user interactions
        to back-end functionality execution.

Manager device implementation is responsible for providing custom communication
logic (in accordance to targeted communication protocol) and appropriate
front-end visualization and user interaction.

During manager execution, device can be in following states:

    * ``STOPPED``

        Manager device is not connected to remote device/component. Changes
        to device configuration parameters are possible.

    * ``STARTING``

        Connection to remote device is trying to be established. In case
        of server/slave devices, listening endpoint is being created.

    * ``STARTED``

        Connection to remote device is established. In case of server/slave
        devices, remote devices can establish connection to server/slave.

    * ``STOPPING``

        Connection to remote device is being closed.

Starting/stopping of devices is done based on user's requests. In case of
enabled ``auto start`` parameter, connection to remote device is repeatedly
automatically started each time connection is lost.

Supported device implementations:

.. toctree::
    :maxdepth: 1

    devices/orchestrator
    devices/monitor
    devices/event
    devices/modbus_master
    devices/modbus_slave
    devices/iec104_master
    devices/iec104_slave
