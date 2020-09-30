Hat Core - Python utility library
=================================

This library is part of Hat Open project - open-source framework of tools and
libraries for developing applications used for remote monitoring, control and
management of intelligent electronic devices such as IoT devices, PLCs,
industrial automation or home automation systems.

Development of Hat Open and associated repositories is sponsored by
Končar - Power Plant and Electric Traction Engineering Inc.
(Končar KET - `<https://www.koncar-ket.hr>`_).

For more information see:

    * `hat-util` documentation - `<https://core.hat-open.com/docs/libraries/util/python.html>`_
    * Hat Core homepage - `<https://core.hat-open.com>`_
    * Hat Core git repository - `<https://github.com/hat-open/hat-core.git>`_

.. warning::

    This project is currently in state of active development. Features,
    functionality and API are unstable.


About
-----

Package `hat-util` provides common utility functions not available
as part of Python standard library. These function are available as parts of
modules:

    * `hat.util.common`

        Extensions of basic builtin python data types.

    * `hat.util.aio`

        Utility functions and data structures providing enhancment of
        `asyncio` library.

    * `hat.util.json`

        Functions related to serialization of JSON data and validation based
        on JSON Schemas.

    * `hat.util.qt`

        Parallel execution of Qt and asyncio threads.
