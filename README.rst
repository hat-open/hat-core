Hat Core - advanced SCADA-like core system components
=====================================================

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

    * hat-util

        Utility module

    * hat-peg

        Parsing expression grammar

    * hat-juggler

        Juggler communication protocol


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
