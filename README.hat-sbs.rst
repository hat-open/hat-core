Hat Core - Simple binary serialization
======================================

This library is part of Hat Open project - open-source framework of tools and
libraries for developing applications used for remote monitoring, control and
management of intelligent electronic devices such as IoT devices, PLCs,
industrial automation or home automation systems.

Development of Hat Open and associated repositories is sponsored by
Končar - Power Plant and Electric Traction Engineering Inc.
(Končar KET - `<https://www.koncar-ket.hr>`_).

For more information see:

    * `hat-sbs` documentation - `<https://core.hat-open.com/docs/libraries/sbs.html>`_
    * Hat Core homepage - `<https://core.hat-open.com>`_
    * Hat Core git repository - `<https://github.com/hat-open/hat-core.git>`_

.. warning::

    This project is currently in state of active development. Features,
    functionality and API are unstable.


About
-----

Simple binary serialization (SBS) features:

    * schema based
    * small schema language optimized for human readability
    * schema re-usability and organization into modules
    * small number of built in types
    * polymorphic data types
    * binary serialization
    * designed to enable simple and efficient implementation
    * optimized for small encoded data size

Example of SBS schema::

    module Module

    Entry(K, V) = Tuple {
        key: K
        value: V
    }

    Collection(K) = Union {
        null: None
        bool: Entry(K, Boolean)
        int: Entry(K, Integer)
        float: Entry(K, Float)
        str: Entry(K, String)
        bytes: Entry(K, Bytes)
    }

    IntKeyCollection = Collection(Integer)

    StrKeyCollection = Collection(String)
