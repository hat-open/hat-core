.. _gui:

GUI Server
==========

GUI Server provides user interface for monitoring and controlling
Hat system functionality in real time. It provides multi-user environment
with authentication and authorization control of available resources.


Running
-------

By installing GUI Server from `hat-gui` package, executable `hat-gui`
becomes available and can be used for starting this component.

    .. program-output:: python -m hat.gui --help


Overview
--------

GUI functionality can be defined according to following components:

.. uml::

    folder "Event Server" as EventServer

    folder "GUI Backend" {
        component "Event Client" as EventClient

        component Server
        component Session <<Session>> as Session

        component Adapter <<Adapter>> as Adapter
        component "Adapter Event Client" <<AdapterEventClient>> as AdapterEventClient
        component "Adapter Session Client" <<AdapterSessionClient>> as AdapterSessionClient
        component "Adapter Session" <<AdapterSession>> as AdapterSession

        component "View Manager" as ViewManager
    }

    folder "GUI Frontend" {
        component Client
        component View
    }

    folder "File system" {
        component "View Dir" as ViewDir
    }

    EventServer <-> EventClient

    Server o-- Session

    Session <-> Client

    Session o-- AdapterSession

    Adapter ..> AdapterSession : create

    AdapterSession <-> AdapterSessionClient

    Session o- AdapterSessionClient

    EventClient <--> AdapterEventClient

    AdapterEventClient <-> Adapter

    Server -> ViewManager

    ViewManager .> ViewDir : get

    Session .> View : send

Functionality is dependent on active connection to Event Server. Adapters,
Server and View Manager are created when connection with Event Server is
established and destroyed if this connection is closed. If connection with
Event Server is closed, GUI will repeatedly try to establish new connection
with currently active Event Server. If connection to Monitor Server could not
be established or is closed, GUI terminates its process execution.


Backend - frontend communication
--------------------------------

Communication between backend and frontend is based on juggler protocol.
Each connection between server and client (`Session`) has got unique local
data. Structure of local data on both client and server side is defined
by JSON schema::

    type: object
    description: |
        keys represent adapter names
    patternProperties:
        ".+":
            description: |
                structure of adapter's local/remote data is defined by
                adapter type

Supported juggler `MESSAGE` messages sent from client to server are::

    definitions:
        login:
            type: object
            required:
                - type
                - name
                - password
            properties:
                type:
                    enum:
                        - login
                name:
                    type: string
                password:
                    type: string
                    description: |
                        this property contains SHA-256 password
                        hash encoded as hex string
        logout:
            type: object
            required:
                - type
            properties:
                type:
                    enum:
                        - logout
        adapter:
            type: object
            required:
                - type
                - name
                - data
            properties:
                type:
                    enum:
                        - adapter
                name:
                    type: string
                    description: adapter instance name
                data:
                    description: |
                        structure of this property is defined by
                        adapter type

Supported juggler `MESSAGE` messages sent from server to client are::

    definitions:
        state:
            type: object
            required:
                - type
                - user
                - view
                - conf
            properties:
                type:
                    enum:
                        - state
                user:
                    type:
                        - string
                        - "null"
                    description: |
                        null represents unsuccessful authentication
                view:
                    type: object
        adapter:
            type: object
            required:
                - type
                - name
                - data
            properties:
                type:
                    enum:
                        - adapter
                name:
                    type: string
                    description: adapter instance name
                data:
                    description: |
                        structure of this property is defined by
                        adapter type

When client establishes new juggler connection with server, initial local
data on server side is ``null``. Immediately after connection is established,
server sends `state` message with `user` ``null`` and initial view.
At any time, client can send `login` or `logout` message. Once server receives
``login`` or ``logout`` message, it should respond with appropriate ``state``
message.

When client successfully authenticates, server will create new `Session`
instance which is responsible for further communication with client. Initial
`state` message delivered to client will contain `view` data and configuration.
Session continuously updates server's local data according to
AdapterSessionClient's local data. It is also responsible for creating adapter
session and bidirectional forwarding of `adapter` messages between frontend
client and adapter client.


Adapters
--------

Adapters are mutually independent providers of server-side functionality and
data exposed to GUI frontends. For providing this functionality and data,
adapters rely primarily on their internal state and communication with Event
Server. Adapter definitions are dynamically loaded during GUI server startup
procedure.

GUI server can be configured to initialize arbitrary number of adapter
instances with their custom configurations which will be validated with
associdated adapter's optional JSON schema. During adapter instance
initialization, each adapter instance is provided with instance of
AdapterEventClient. AdapterEventClient provides proxy interface to active
Event client connection which enables communication with Event Server
in accordance with adapter's event type subscription.

Adapter is responsible for creating new instances of AdapterSessions
associated with backend-frontend communication session. During initialization
of AdapterSession, adapter is provided with appropriate instance of
AdapterSessionClient which can be used by Adapter or AdapterSession for
communication with individual GUI frontends. AdapterSessionClient enables
full juggler communication (exchange of local/remote state and asynchronous
message communication) appropriate for associated AdapterSession.

Implementation of single adapter is usually split between Adapter
implementation and AdapterSession implementation where Adapter encapsulates
shared data and AdapterSession encapsulates custom data and functionality
specific for each Session instance. Additionally, each AdapterSession is
responsible for enforcing fine grained authorization rules in accordance to
user authenticated with associated AdapterSessionClient.

Adapters available as part of `hat-gui` package:

    .. toctree::
       :maxdepth: 1

       adapters/dummy


Views
-----

Views are collection of JavaScript code and other frontend resources
responsible for graphical representation of adapters state and interaction
with user. Each view is represented with content of file system directory.

`ViewManager` is server side component which is used for loading view's
resources. Each file inside view's directory (or subdirectory) is identified
with unix file path relative to view's directory. Each file is read from
file system and encoded as string based on file extension:

    * `.js`, `.css`, `.txt`

        files are read and encoded as `utf-8` encoded strings

    * `.json`, `.yaml`, `.yml`

        files are read as json or yaml files and encoded as `utf-8` json data
        representation

    * `.svg`, `.xml`

        files are read as xml data and encoded as `utf-8` json data
        representing equivalent virtual tree

        .. todo::

            better definition of transformation between xml and virtual
            tree data

    * all other files

        files are read as binary data and encoded as `base64` strings

Server chooses client's view depending on authenticated user and configuration
of first role associated with user. This view's resources and configuration
is obtained from `ViewManager`. Responsibility of `ViewManager` is to provide
current view's data and configuration as available on file system in the
moment when server issued request for these resources. If view directory
contains `schema.{yaml|yml|json}`, it is used as JSON schema for validating
view's configuration.

.. todo::

    future improvements:

        * zip archives as view bundles
        * 'smart' ViewManager with watching view directory and conf for changes
          and preloading resources on change

Once client receives new `state` message, it will evaluate JavaScript code from
view's `index.js`. This code is evaluated inside environment which contains
global constant ``hat``. When evaluation is finished, environment should
contain global values ``init``, ``vt`` and ``destroy``.

Client bounds juggler connection's local data to default renderer's
``['local']`` path and remote data to default renderer's ``['remote']`` path.
Constant ``hat``, available during execution of `index.js`, references object
with properties:

    * ``conf``

        view's configuration

    * ``user``

        authenticated user identifier

    * ``view``

        view's data

    * ``conn``

        object representing connection with server with properties:

            * `onMessage`

                property which references function called each time new
                `adapter` message is received (callback receives arguments
                `adapter` and `msg` which reference content of `adapter`
                message)

            * `login(name, password)`

                login method

            * `logout()`

                logout method

            * `send(adapter, msg)`

                method for sending `adapter` messages

When evaluation finishes, environment should contain:

    * ``init``

        optional initialization function which is called immediately after
        evaluation of `index.js` finishes (this function has no input arguments
        and its return value is ignored)

    *  ``vt``

        function called each time global renderer's state changes (this
        function has no input arguments and it should return virtual tree data)

    * ``destroy``

        optional function called prior to evaluation of other view's `index.js`
        (this function has no input arguments and its return value is ignored)

Views available as part of `hat-gui` package:

    .. toctree::
       :maxdepth: 1

       views/dummy


Python implementation
---------------------

.. automodule:: hat.gui.common

.. automodule:: hat.gui.view

.. automodule:: hat.gui.server

.. automodule:: hat.gui.vt
