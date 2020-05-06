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

    * Hat Open homepage - ``in development``
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

Python packages require Python 3.8 and can be installed with `pip`::

    $ pip install <package-name>

where ``package-name`` is one of following:

    * `hat-util <https://pypi.org/project/hat-util>`_
      (`util docs <https://core.hat-open.com/docs/libraries/util.html>`_)

        Utility module

    * `hat-peg <https://pypi.org/project/hat-peg>`_
      (`peg docs <https://core.hat-open.com/docs/libraries/peg.html>`_)

        Parsing expression grammar

    * `hat-sbs <https://pypi.org/project/hat-sbs>`_
      (`sbs docs <https://core.hat-open.com/docs/libraries/sbs.html>`_)

        Chatter communication protocol

    * `hat-chatter <https://pypi.org/project/hat-chatter>`_
      (`chatter docs <https://core.hat-open.com/docs/libraries/chatter.html>`_)

        Simple binary serialization

    * `hat-juggler <https://pypi.org/project/hat-juggler>`_
      (`juggler docs <https://core.hat-open.com/docs/libraries/juggler.html>`_)

        Juggler communication protocol

    * `hat-duktape <https://pypi.org/project/hat-duktape>`_
      (`duktape docs <https://core.hat-open.com/docs/libraries/duktape.html>`_)

        Python Duktape JS wrapper

    * `hat-sqlite3 <https://pypi.org/project/hat-sqlite3>`_

        Hat specific sqlite3 build

    * `hat-asn1 <https://pypi.org/project/hat-asn1>`_
      (`asn1 docs <https://core.hat-open.com/docs/libraries/asn1.html>`_)

        ASN.1 parser and encoder

    * `hat-drivers <https://pypi.org/project/hat-drivers>`_
      (`drivers docs <https://core.hat-open.com/docs/libraries/drivers/index.html>`_)

        Communication drivers

    * `hat-orchestrator <https://pypi.org/project/hat-orchestrator>`_
      (`orchestrator docs <https://core.hat-open.com/docs/components/orchestrator.html>`_)

        Simple cross-platform daemon/service manager

    * `hat-monitor <https://pypi.org/project/hat-monitor>`_
      (`monitor docs <https://core.hat-open.com/docs/components/monitor.html>`_)

        Redundancy and service discovery server

    * `hat-event <https://pypi.org/project/hat-event>`_
      (`event docs <https://core.hat-open.com/docs/components/event/index.html>`_)

        Event pub/sub communication and storage

    * `hat-gateway <https://pypi.org/project/hat-gateway>`_
      (`gateway docs <https://core.hat-open.com/docs/components/gateway/index.html>`_)

        Remote communication device gateway

    * `hat-gui <https://pypi.org/project/hat-gui>`_
      (`gui docs <https://core.hat-open.com/docs/components/gui/index.html>`_)

        GUI server

    * `hat-translator <https://pypi.org/project/hat-translator>`_
      (`translator docs <https://core.hat-open.com/docs/components/translator.html>`_)

        Configuration transformation interface


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

        Juggler client library


Build
-----

Build tool used for Hat is pydoit (`http://pydoit.org/`). It can be installed
with `pip` by running::

    $ pip install doit

For listing available doit tasks, use::

    $ doit list

Default task::

    $ doit

creates `dist` folder containing built packages.


Dependencies
''''''''''''

Package managers used for managing dependencies:

    * pacman

        Package manager of Arch linux distribution. Available on
        Windows as part of `msys2` (`<http://www.msys2.org/>`_).

    * pip

        Package manager available as part of CPython installation.

    * yarn

        Package manager for NodeJS.

List of all dependencies for building and running hat components is available
in:

    * requirements.pacman.win.txt (windows only)
    * requirements.pacman.linux.txt (archlinux only)
    * requirements.pip.txt
    * package.json

Python code targets CPython 3.8 only.


Documentation
-------------

Documentation can be built with::

    $ doit docs

which creates `build/docs` folder containing documentation.
