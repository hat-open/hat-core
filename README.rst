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
    * Hat Core homepage - `<https://hat-open.github.io/hat-core>`_
    * Hat Core documentation - `<https://hat-open.github.io/hat-core/docs>`_
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
      (`util docs <https://hat-open.github.io/hat-core/docs/libraries/util.html>`_)

        Utility module

    * `hat-peg <https://pypi.org/project/hat-peg>`_
      (`peg docs <https://hat-open.github.io/hat-core/docs/libraries/peg.html>`_)

        Parsing expression grammar

    * `hat-sbs <https://pypi.org/project/hat-sbs>`_
      (`sbs docs <https://hat-open.github.io/hat-core/docs/libraries/sbs.html>`_)

        Chatter communication protocol

    * `hat-chatter <https://pypi.org/project/hat-chatter>`_
      (`chatter docs <https://hat-open.github.io/hat-core/docs/libraries/chatter.html>`_)

        Simple binary serialization

    * `hat-juggler <https://pypi.org/project/hat-juggler>`_
      (`juggler docs <https://hat-open.github.io/hat-core/docs/libraries/juggler.html>`_)

        Juggler communication protocol


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

List of all dependencies for building and running hat components is available
in:

    * requirements.pacman.win.txt (windows only)
    * requirements.pacman.linux.txt (archlinux only)
    * requirements.pip.txt

Python code targets CPython 3.8 only.


Documentation
-------------

Documentation can be built with::

    $ doit docs

which creates `build/docs` folder containing documentation.
