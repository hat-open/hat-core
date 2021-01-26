Hat Core - Juggler communication protocol
=========================================

This library is part of Hat Open project - open-source framework of tools and
libraries for developing applications used for remote monitoring, control and
management of intelligent electronic devices such as IoT devices, PLCs,
industrial automation or home automation systems.

Development of Hat Open and associated repositories is sponsored by
Končar - Power Plant and Electric Traction Engineering Inc.
(Končar KET - `<https://www.koncar-ket.hr>`_).

For more information see:

    * `hat-juggler` documentation - `<https://core.hat-open.com/docs/libraries/juggler/python.html>`_
    * Hat Core homepage - `<https://core.hat-open.com>`_
    * Hat Core git repository - `<https://github.com/hat-open/hat-core.git>`_

.. warning::

    This project is currently in state of active development. Features,
    functionality and API are unstable.


About
-----

Chatter is communication protocol used for communication between Hat
back-end services and web-based front-ends. Some of key features:

    * based on WebSocket communication
    * symmetrical full duplex (peer-to-peer) communication
    * unsolicited message passing
    * local/remote JSON state synchronization based on JSON Patch
