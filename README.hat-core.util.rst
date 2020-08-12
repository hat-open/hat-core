Hat Core - JavaScript utility library
=====================================

This library is part of Hat Open project - open-source framework of tools and
libraries for developing applications used for remote monitoring, control and
management of intelligent electronic devices such as IoT devices, PLCs,
industrial automation or home automation systems.

Development of Hat Open and associated repositories is sponsored by
Končar - Power Plant and Electric Traction Engineering Inc.
(Končar KET - `<https://www.koncar-ket.hr>`_).

For more information see:

    * `@hat-core/util` documentation - `<https://core.hat-open.com/docs/libraries/util/javascript.html>`_
    * Hat Core homepage - `<https://core.hat-open.com>`_
    * Hat Core git repository - `<https://github.com/hat-open/hat-core.git>`_

.. warning::

    This project is currently in state of active development. Features,
    functionality and API are unstable.


About
-----

Utility library for manipulation of JSON data.

Main characteristics:

  * input/output data types are limited to JSON data, functions and
    `undefined` (sparse arrays and complex objects with prototype chain are
    not supported)

  * functional API with curried functions (similar to ramdajs)

  * implementation based on natively supported browser JS API

  * scope limited to most used functions in hat projects

  * usage of `paths` instead of `lenses`
