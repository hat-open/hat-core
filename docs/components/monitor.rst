.. _monitor:

Monitor Server
==============

Monitor Server is component responsible for providing infrastructure necessary
for multiple redundant component execution. Additionally, Monitor Server
provides centralized registry of running components in single system which can
be used for service discovery.

.. warning::

    Monitor Server functionality is defined under assumptions:

        * components running as part of single system are trusted and
          implemented according to specifications
        * communication channels between components on single computing
          node are reliable

    Redundancy mechanisms provided by Monitor Server do not provide
    reliability in case of possible component malfunctions due to
    implementation errors.


Running
-------

By installing Monitor Server from `hat-monitor` package, executable
`hat-monitor` becomes available and can be used for starting this component.

    .. program-output:: python -m hat.monitor.server --help

Additionally, `hat-monitor` package provides implementation of library which
can be used as basis for communication between components and Monitor Server.
This library is available in :mod:`hat.monitor.client` module.


Communication model
-------------------

Monitor Server provides n-node redundancy architecture based on
:ref:`chatter <chatter>` protocol (structure of communication messages is
defined in `HatMonitor` package). It is based on server-client communication
between components and monitor server. There also exists horizontal peer
communication between multiple monitor servers which enables forming of
single system based on multiple distributed computing nodes. It is assumed
that, for each system, single computing node runs single instance of Monitor
Server and unlimited number of components that connect to local Monitor Server.
Each node's Monitor Server establishes communication with other nodes' Monitor
Server through single master Monitor Server. Hierarchy of Monitor Servers
which can perform functionality of master is configured statically with
configuration options available to each Monitor Server on its startup.

Entities participating in communication between components and local monitor
server:

    * Client

        Component proclaiming its existence to the server, discovering
        other components and participating in redundancy algorithm.

    * Server

        Local monitor server providing global components state to all local
        clients and providing user interface.

Entities participating in 'horizontal' communication between Monitor Servers:

    * Master

        Monitor Server responsible for execution of the redundancy algorithm
        and notifying other Monitor Servers about the current global state of
        the entire system.

    * Slave

        Monitor Server responsible for notifying master about its current local
        state and delegating master's notifications to its server entity.

Monitor Server uses two different independent listening sockets for
client-server and master-slave communication.

If we represent components with `Cn` and Monitor Servers with `Mn`, where
master hierarchy of `M1 > ... > Mn` is presumed, an example of a single system
monitor communication can be viewed as:

    .. graphviz::
        :align: center

        graph {
            bgcolor=transparent;
            layout=neato;
            node [fontname="Arial"];
            {
                node [shape=box];
                M1; M2; M3; M4;
            }
            {
                node [shape=oval];
                C1; C2; C3; C4; C5; C6; C7; C8; C9; C10; C11; C12;
            }
            {
                edge [dir=forward, style=bold, len=2];
                M2 -- M1;
                M3 -- M1;
                M4 -- M1;
            }
            {
                edge [dir=forward, style="bold,dashed", len=2];
                M3 -- M2;
                M4 -- M2;
                M4 -- M3;
            }
            {
                edge [dir=both, arrowsize=0.5];
                M1 -- C1;
                M1 -- C2;
                M1 -- C3;
                M2 -- C4;
                M2 -- C5;
                M2 -- C6;
                M3 -- C7;
                M3 -- C8;
                M3 -- C9;
                M4 -- C10;
                M4 -- C11;
                M4 -- C12;
            }
        }


Component information
---------------------

Component information is basic structure of properties that describe each
component included in system. It is initially created on local Monitor Server
and later updated by master Monitor Server. Collection of all components
information associated with clients connected to local Monitor Server and
calculated by local Monitor Server is called local state. Collection of all
components information in single system calculated by master Monitor server is
called global state. Each Monitor Server provides global state to its local
clients.

Properties included in a component information:

    * `cid`

        Component id assigned to client by its local Monitor Server.

    * `mid`

        Monitor id identifying local Monitor Server (assigned to local Monitor
        Server by master). Value ``0`` indicates Monitor Server which is master
        or is not connected to remote master.

    * `name`

        User provided identifier of component. This entry is used only for
        UI presentation purposes and logging but it is recommended to
        use unique identifiers for each component instance. This property
        is assigned by client.

    * `group`

        String identifier by which components are grouped while blessing
        calculation algorithm is applied (see `Blessing algorithm`_). This
        property is assigned by client.

    * `address`

        Component's address which other components use to connect to the
        component. This property is optional and is assigned by client.

    * `rank`

        Component's rank - used by `Blessing algorithm`_. This property is
        initially assigned by local Monitor Server but can later be changed by
        any Monitor Server.

    * `blessing`

        Optional number used as unique token assigned and changed by master
        Monitor Server (see `Component lifetime`_).

    * `ready`

        Optional number used as unique token assigned and changed by client
        (see `Component lifetime`_).


Master slave communication
--------------------------

Horizontal communication between Monitor Servers is hierarchically ordered.
Each Monitor Server knows its superiors' addresses. If ``M1 > M2 > M3``,
then ``M1`` doesn't know any other monitor address; ``M2`` knows the address
of ``M1``; ``M3`` knows addresses of ``M1`` and ``M2`` in that order.

Each Monitor Server's configuration contains zero or more other Monitor
Server addresses. These other servers are "superior" to the monitor server. A
monitor server will always try to maintain an active connection with exactly
one of its superiors. The addresses list is ordered by priority meaning that if
the Monitor Server isn't connected to a superior, it tries to connect to the
first monitor server in the list. If the connection fails, it tries the second
one and so on. If it can't connect to any of its superiors, it can proclaim
itself as master. The connecting to master process should continue even if the
Monitor Server is master or it is not connected to its first superior. The
connecting loop should be executed at least 2 or 3 times before the timeout can
be used. The timeout should be kept small.

Once a slave Monitor Server connects to the Master Monitor server it sends its
local state to the master and keeps notifying the master about any change in
its local state while the connection is active. The master gathers all local
states and generates its global state which it then transmits to all its
slaves and keeps notifying them of any change. Master also identifies each
Monitor Server with unique monitor identifier (`mid`) which is provided to
slave together with global state. It is important to note that only master
Monitor Server calculates blessing token state for each component.

Every Monitor Server is responsible for starting master listening socket
immediately after startup. While Monitor Server isn't operating in master mode,
all connections made to master listening socket will be closed immediately
after their establishment - this behavior will indicate to connecting Monitor
Server that its superior is not currently master.

Messages used in master slave communications are:

    +--------------------+----------------------+-----------+
    |                    | Conversation         |           |
    | Message            +-------+------+-------+ Direction |
    |                    | First | Last | Token |           |
    +====================+=======+======+=======+===========+
    | MsgSlave           | T     | T    | T     | s |arr| m |
    +--------------------+-------+------+-------+-----------+
    | MsgMaster          | T     | T    | T     | m |arr| s |
    +--------------------+-------+------+-------+-----------+
    | MsgSetRank         | T     | T    | T     | s |arr| m |
    +--------------------+-------+------+-------+-----------+

where `s` |arr| `m` represents slave to master communication and `m` |arr| `s`
represents master to slave communication. When new connection is established,
master should immediately associate new `mid` with connection and send
`MsgMaster`. After slave receives this initial `MsgMaster`, it should send
`MsgSlave` with local state updated with newly received `mid`. Each
communicating entity (master or slave) should send new state message
(`MsgMaster` or `MsgSlave`) if any data obtained from `MsgSlave` or `MsgMaster`
changes. Sending of `MsgMaster` and `MsgSlave` should be implemented
independent of receiving messages from associated entity. Implementation
of master should not be dependent on receiving initial `MsgSlave` and should
continue sending `MsgMaster` on every state change even if no `MsgSlave` is
received.

.. |arr| unicode:: U+003E


Server client communication
---------------------------

Vertical communication between client and server enables bidirectional
asynchronous exchange of component information data. Client is responsible
for providing `name`, `group`, `address` and `ready` properties initially and
on every change. Server provides global state to each connected client and
each client's component id (`cid`) and monitor id (`mid`). If any part of
state available to server changes (including token changes), server sends
updated state to all clients. Client can also request change for information
provided to server at any time.

Messages used in server client communications are:

    +--------------------+----------------------+-----------+
    |                    | Conversation         |           |
    | Message            +-------+------+-------+ Direction |
    |                    | First | Last | Token |           |
    +====================+=======+======+=======+===========+
    | MsgClient          | T     | T    | T     | c |arr| s |
    +--------------------+-------+------+-------+-----------+
    | MsgServer          | T     | T    | T     | s |arr| c |
    +--------------------+-------+------+-------+-----------+

where `c` |arr| `s` represents client to server communication and `s` |arr|
`c` represents server to client communication. When new connection is
established, each communicating entity (server or client) server immediately
sends initial state message (`MsgServer` or `MsgClient`) and should send new
state messages when any data obtained from `MsgServer` or `MsgClient` changes.
Sending of `MsgServer` and `MsgClient` should be implemented independent of
receiving messages from associated entity. Implementation of server should not
be dependent on receiving initial `MsgClient` and should continue sending
`MsgServer` on every state change even if no `MsgClient` is received.


Component lifetime
------------------

For most components, connection to local Monitor Server is mandatory for
providing implemented functionality. Because of this, component usually connects
to local Monitor Server during startup and preserves this active connection
during entire component run lifetime. If this connection is closed for any
reason, process also terminates. This behavior is not mandated.

Components which connect to Monitor Server participate in redundancy
supervised by master Monitor Server. Redundancy utilizes two tokens:

    * `blessing` token

        This token is controlled exclusively by master Monitor Server. If
        connection to master is not established, token's value is not set.

    * `ready` token

        This token is controlled exclusively by client. It will match
        `blessing` value only if component is ready to provide its primary
        functionality. At any time, if component stops providing primary
        functionality, it should revoke this token.

Each component determines if it should provide primary functionality based on
global state provided by local Monitor Server. If client's component
information contains `blessing` and `ready` token with same value, component
can provide primary functionality. If, at any time, these values do not match,
component should stop its usual activity which is indicated by client's
revoking of `ready` flag.


Blessing algorithm
------------------

Blessing algorithm determines value of each component's `blessing` token. This
calculation is performed on master Monitor Server and should be executed
each time any part of global state changes. This calculation should be
integrated part of state change and thus provide global state consistency.

Monitor Server implements multiple algorithms for calculating value of blessing
token. Each component `group` can have different associated blessing algorithm
and all groups that don't have associated blessing algorithm use default
algorithm. Group's associated algorithms and default algorithm are provided
to Monitor Server as configuration parameters during its startup.

Calculation of `blessing` token values is based only on previous global state
and new changes that triggered execution of blessing algorithm.

Currently supported algorithms:

    * BLESS_ALL

        This simple algorithm provides continuous blessing to all components
        in associated group. Blessing is never revoked.

    * BLESS_ONE

        In each group with this algorithm associated, there can be only one
        highlander and component with issued blessing token. For determining
        which component can receive blessing token, component's rank is used.
        Components with mathematically lower rank value have higher priority
        in obtaining blessing token. If there exist more than one component with
        highest priority than one with already set blessing token is chosen.
        If neither of component have already set blessing token, than one of
        components with lowest `mid` value is chosen. Once component which can
        obtain blessing token is chosen, if chosen component doesn't already
        have blessing token, master revokes previously issued blessing token
        from other component in the same group and waits for all components in
        the same group to revoke theirs ready tokens. Only once all other
        components revoke their ready tokens, master issues new blessing token
        to chosen component.


Components rank
---------------

Association of component's rank is initial responsibility of component's
local Monitor Server. Each Monitor Server should associate same rank as was
last rank value associated with previously active client connection with
same `name` and `group` values as newly established connection. If such
previously active connection does not exist, default rank value, as specified
by Monitor Server's configuration, is applied. After initial rank value is
associated with client and its `ComponentInfo`, all Monitor Servers can
request change of rank for all `ComponentInfo` s. These changes should be
monitored and cached by local Monitor Servers in case connection to component
is lost and same component tries to establish new connection. This cache is
maintained for duration of single Monitor Server process execution and is not
persisted between different Monitor Server processes.


User interface
--------------

As secondary functionality, Monitor Server provides web-based user interface
for monitoring global components state and controlling component's rank.
Implementation of this functionality is split into server-side web backend and
web frontend exchanging communication messages based on
:ref:`juggler <juggler>` communication protocol.


Backend to frontend communication
'''''''''''''''''''''''''''''''''

Backend provides to frontends all information that is made available by server
to clients. When this information changes, all frontends are notified of
this change. Current state of `mid` and all components is set and continuously
updated as part of server's juggler local data.

After new Juggler connection is established, backend will immediately set
juggler local data defined by JSON schema:

.. code:: yaml

    "$schema": "http://json-schema.org/schema#"
    type: object
    required:
        - mid
        - components
    properties:
        mid:
            type: integer
        components:
            type: array
            items:
                type: object
                required:
                    - cid
                    - mid
                    - name
                    - group
                    - address
                    - rank
                    - blessing
                    - ready
                properties:
                    cid:
                        type: integer
                    mid:
                        type: integer
                    name:
                        type: string
                    group:
                        type: string
                    address:
                        type:
                            - string
                            - "null"
                    rank:
                        type: integer
                    blessing:
                        type:
                            - integer
                            - "null"
                    ready:
                        type:
                            - integer
                            - "null"

Server doesn't send additional `MESSAGE` juggler messages.


Frontend to backend communication
'''''''''''''''''''''''''''''''''

This communication is used primary for enabling user control of components'
ranks. At any time, frontend can send `set_rank` message to backend requesting
change of rank for any available component (event those that are not local to
backend's Monitor Server). These massages are transmitted as juggler's
`MESSAGE` messages defined by JSON schema:

.. code:: yaml

    "$schema": "http://json-schema.org/schema#"
    oneOf:
        - "$ref": "#/definitions/set_rank"
    definitions:
        set_rank:
            type: object
            required:
                - type
                - payload
            properties:
                type:
                    enum:
                        - set_rank
                payload:
                    type: object
                    required:
                        - cid
                        - mid
                        - rank
                    properties:
                        cid:
                            type: integer
                        mid:
                            type: integer
                        rank:
                            type: integer

Client's juggler local data isn't changed during communication with server (it
remains `null`).


Future features
---------------

.. todo::

    * configurable master retry count and timeouts
    * optional connection to monitor/event server

        * mapping of current status to events
        * listening for control events


Python implementation
---------------------

Common
''''''

.. automodule:: hat.monitor.common


Client
''''''

.. automodule:: hat.monitor.client


Blessing
''''''''

.. automodule:: hat.monitor.server.blessing


Server
''''''

.. automodule:: hat.monitor.server.server


Master
''''''

.. automodule:: hat.monitor.server.master


UI
''

.. automodule:: hat.monitor.server.ui
