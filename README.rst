Hat Core - remote control and monitoring framework core
=======================================================

Hat Open is open-source framework of tools and libraries for developing
applications used for remote monitoring, control and management of
intelligent electronic devices such as IoT devices, PLCs, industrial
automation or home automation systems.

Hat Core is part of Hat Open providing collection of components and libraries
on which Hat Open system is based.

Development of Hat Open and associated repositories is sponsored by
Končar - Power Plant and Electric Traction Engineering Inc.
(Končar KET - `<https://www.koncar-ket.hr>`_).

For more information see:

    * Hat Core homepage - `<https://core.hat-open.com>`_
    * Hat Core documentation - `<https://core.hat-open.com/docs>`_
    * Hat Core git repository - `<https://github.com/hat-open/hat-core.git>`_
    * Hat Core issues - `<https://github.com/hat-open/hat-core/issues>`_

.. warning::

    This project is currently in state of active development. Features,
    functionality and API are unstable.


Installation
------------

Hat Open consists of multiple interconnected parts. Each part implements a
specific functionality. For easier reusability, provided implementation is
split into multiple packages:


Python packages
'''''''''''''''

Python packages require Python 3.8 or 3.9 and can be installed with `pip`::

    $ pip install <package-name>

where ``package-name`` is one of following:

    * `hat-util <https://pypi.org/project/hat-util>`_

        Utility library

    * `hat-aio <https://pypi.org/project/hat-aio>`_

        Async utility library

    * `hat-json <https://pypi.org/project/hat-json>`_

        JSON library

    * `hat-qt <https://pypi.org/project/hat-qt>`_

        Qt utility library

    * `hat-peg <https://pypi.org/project/hat-peg>`_

        Parsing expression grammar

    * `hat-stc <https://pypi.org/project/hat-stc>`_

        Statechart engine

    * `hat-sbs <https://pypi.org/project/hat-sbs>`_

        Simple binary serialization

    * `hat-chatter <https://pypi.org/project/hat-chatter>`_

        Chatter communication protocol

    * `hat-juggler <https://pypi.org/project/hat-juggler>`_

        Juggler communication protocol

    * `hat-duktape <https://pypi.org/project/hat-duktape>`_

        Python Duktape JS wrapper

    * `hat-sqlite3 <https://pypi.org/project/hat-sqlite3>`_

        Hat specific sqlite3 build

    * `hat-asn1 <https://pypi.org/project/hat-asn1>`_

        ASN.1 parser and encoder

    * `hat-drivers <https://pypi.org/project/hat-drivers>`_

        Communication drivers

    * `hat-syslog <https://pypi.org/project/hat-syslog>`_

        Syslog server and logging handler

    * `hat-orchestrator <https://pypi.org/project/hat-orchestrator>`_

        Simple cross-platform daemon/service manager

    * `hat-monitor <https://pypi.org/project/hat-monitor>`_

        Redundancy and service discovery server

    * `hat-event <https://pypi.org/project/hat-event>`_

        Event pub/sub communication and storage

    * `hat-gateway <https://pypi.org/project/hat-gateway>`_

        Remote communication device gateway

    * `hat-gui <https://pypi.org/project/hat-gui>`_

        GUI server


JavaScript packages
'''''''''''''''''''

JavaScript packages can be installed with `npm`::

    $ npm install <package-name>

where ``package-name`` is one of following:

    * `@hat-core/util <https://www.npmjs.com/package/@hat-core/util>`_

        Utility module

    * `@hat-core/renderer <https://www.npmjs.com/package/@hat-core/renderer>`_

        Virtual DOM renderer

    * `@hat-core/future <https://www.npmjs.com/package/@hat-core/future>`_

        Async Future implementation

    * `@hat-core/juggler <https://www.npmjs.com/package/@hat-core/juggler>`_

        Juggler communication protocol client library


Development
-----------

Platforms supported as development environment include Linux (possibly other
POSIX systems) and Windows (with MSYS2 and CPython).


Platform specific prerequisites
'''''''''''''''''''''''''''''''

* Archlinux::

    $ pacman -S $(< requirements.archlinux.txt)

* Ubuntu::

    $ apt install $(< requirements.ubuntu.txt)

* Windows::

    $ pacman -S $(< requirements.msys2.txt)


Python prerequisites
''''''''''''''''''''

::

    $ pip install -r requirements.pip.txt


Build
'''''

Build tool used for Hat is pydoit (`http://pydoit.org/`). It is included
as one of python prerequisites and should be available after `pip`
requirements installation.

For listing available doit tasks, use::

    $ doit list

Default task::

    $ doit

creates `dist` folder containing built packages.


Documentation
'''''''''''''

Documentation can be built with::

    $ doit docs

which creates `build/docs` folder containing documentation.


Tests
'''''

Tests can be run with `doit` task ``test``.

* Unit tests::

    $ doit test test_unit

* System tests::

    $ doit test test_sys

* Performance tests::

    $ doit test test_perf


License
-------

Copyright 2020-2021 Hat Open AUTHORS

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
