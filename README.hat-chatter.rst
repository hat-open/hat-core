Hat Core - Chatter communication protocol
=========================================

This library is part of Hat Open project - open-source framework of tools and
libraries for developing applications used for remote monitoring, control and
management of intelligent electronic devices such as IoT devices, PLCs,
industrial automation or home automation systems.

Development of Hat Open and associated repositories is sponsored by
Končar - Power Plant and Electric Traction Engineering Inc.
(Končar KET - `<https://www.koncar-ket.hr>`_).

For more information see:

    * `hat-chatter` documentation - `<https://core.hat-open.com/docs/libraries/chatter/python.html>`_
    * Hat Core homepage - `<https://core.hat-open.com>`_
    * Hat Core git repository - `<https://github.com/hat-open/hat-core.git>`_

.. warning::

    This project is currently in state of active development. Features,
    functionality and API are unstable.


About
-----

Chatter is communication protocol used for communication between Hat
components. Some of key features:

    * based on TCP (with optional TLS)
    * binary serialization based on
      `SBS encoding <https://core.hat-open.com/docs/libraries/sbs/index.html>`_
    * message based conversations (independent message exchange streams)
    * full duplex communication
    * unique message identification
    * token passing session control
    * closed connection detection
