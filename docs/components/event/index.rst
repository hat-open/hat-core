.. _event:

Event Server
============

Event Server is a central component responsible for registering, processing,
storing and providing access to events.


Running
-------

By installing Event Server from `hat-event` package, executable `hat-event`
becomes available and can be used for starting this component.

    .. program-output:: python -m hat.event.server --help


Event
-----

Event is a generic data structure used for communication and storage of relevant
changes happening through time in a Hat system. For example, event can represent
a data change triggered by a device outside of the system, or an inner
notification created by a component inside the system. Each event is immutable
and uniquely identified by its event id. Event Server is the only component
responsible for creating events - all other components shall request Event
Server to create a new event.

Event data structure:

    * id

        A unique Event identifier containing Event Server identifier and event
        instance identifier. This property is always set by the server.

    * type

        Type is a user (client) defined list of strings. Semantics of the
        list's elements and their position in the list is determined by the user
        and is not predefined by the Event server. This list should be used as
        the main identifier of the occurred event's type. Each component
        registering an event should have its own naming convention defined
        which does not collide with other components' naming conventions. This
        property is set by the user while registering an event. Subtypes
        ``?`` and ``*`` are not allowed as parts of event type.

        When used in querying and subscription, this property has additional
        semantics. Any string in the list can be replaced with ``?`` while the
        last string can also be replaced with ``*``. Replacements must
        substitute an entire string in the list. The semantics of these
        replacements are:

            * The string ``?``

                is matched with a single arbitrary string.

            * The string ``*``

                is matched with any number (zero or more) of arbitrary strings.

    * timestamp

        This property determines the moment when the event was registered on
        the server. It is always set by the server.

    * source timestamp

        This property is optional. It represents the moment the Event occurred
        as detected by the source of the Event. It is always set by the client.

    * payload

        This property is optional. It can be used to provide additional data
        bound to an event. The payload property is always set by the client
        registering the event. Its contents are determined by the Event's
        **type** and can be decoded by clients who understand Events of that
        **type**. Payload can be encoded as binary data, JSON data or SBS
        encoded data. Event server doesn't decode payload while receiving
        event requests, storing events or providing query results. Payload can
        be optionally decoded by Event Server's modules.


Server - Client communication
-----------------------------

Communication between server and client is based on chatter communication
utilizing following messages:

    +--------------------+----------------------+-----------+
    |                    | Conversation         |           |
    | Message            +-------+------+-------+ Direction |
    |                    | First | Last | Token |           |
    +====================+=======+======+=======+===========+
    | MsgSubscribe       | T     | T    | T     | c |arr| s |
    +--------------------+-------+------+-------+-----------+
    | MsgNotify          | T     | T    | T     | s |arr| c |
    +--------------------+-------+------+-------+-----------+
    | MsgRegisterReq     | T     | T/F  | T     | c |arr| s |
    +--------------------+-------+------+-------+-----------+
    | MsgRegisterRes     | F     | T    | T     | s |arr| c |
    +--------------------+-------+------+-------+-----------+
    | MsgQueryReq        | T     | F    | T     | c |arr| s |
    +--------------------+-------+------+-------+-----------+
    | MsgQueryRes        | F     | T    | T     | s |arr| c |
    +--------------------+-------+------+-------+-----------+

.. |arr| unicode:: U+003E

Actions available to clients which are directly mapped to exchange of
communication messages:

    * subscribe

        A client can, at any time, subscribe to Events of certain types by
        sending a subscribe message (`MsgSubscribe`) to the server. After
        server receives subscribe message, it will spontaneously notify the
        client (by sending `MsgNotify`) whenever an Event occurs with the
        **type** matched to any **type** in the subscription message. Matching
        is done as described in event's type property including the ``?`` and
        ``*`` options. A client can send as many subscribe messages as it
        wants, each new subscription message implicitly invalidates previous
        subscriptions. Initially, after new connection between server and
        client is established, client isn't subscribed to any events. Both
        subscribe and notify messages can be sent at any time independently
        of other communication messages. Events that are notified by single
        `MsgNotify` are mutually unrelated.

    * register event

        A client can, at any time, send new request for event registration.
        Those register requests are sent as part of `MsgRegisterReq` message.
        Single `MsgRegisterReq` may contain an arbitrary number of registration
        requests which are all registered at the same time. Single register
        event contains event type; and optional source timestamp and payload.
        Upon receiving `MsgRegisterReq`, it is responsibility of a server to
        create new event for each register event. All events created based on a
        single `MsgRegisterReq` have the same timestamp. If a client doesn't
        end chatter conversation (`MsgRegisterReq` last flag is false),
        once associated events are created server will respond with
        `MsgRegisterRes` and end conversation. For each register event in
        `MsgRegisterReq`, associated `MsgRegisterRes` contains newly created
        event, or information about event registration failure.

    * query events

        At any time, client can initiate new event query by sending
        `MsgQueryReq` message. Upon receiving query request, server will
        provide all available events that match query criteria as part
        of single `MsgQueryRes`. Single query request can contain multiple
        filter conditions which ALL must be met for all events provided to
        client as query result. Query request contains:

        * ids - optional filter condition

            If set, only events with ids which are defined as part of filter
            condition are matched.

        * types - optional filter condition

            List of event types. If set, event type has to match at least one
            type from the list. Matching is done as defined in event's **type**
            property description - including the ``?`` and ``*`` options.

        * from timestamp - optional filter condition

            If set, only events with **timestamp** greater than or equal are
            matched.

        * to timestamp - optional filter condition

            If set, only events with **timestamp** lower than or equal are
            matched.

        * from source timestamp - optional filter condition

            If set, only events with **source timestamp** defined, and greater
            than or equal, are matched.

        * to source timestamp - optional filter condition

            If set, only events with **source timestamp** defined, and lower
            than or equal, are matched.

        * payload - optional filter condition

            If set, only events with **payload** defined and whose **payload**
            is the same as the query's **payload** are matched.

        * order

            Can be set to 'ascending' or 'descending'. If set to 'ascending',
            matched Events will be returned ordered from the earliest
            to the latest dependent on their **timestamp** or
            **source timestamp** (this choice is determined by the **order by**
            property of the query). Earliest meaning lower timestamp, latest
            meaning greater timestamp. If set to descending the same logic
            applies, but the order is reversed.

        * order by

            Can be set to 'timestamp' or 'source timestamp'. Ordering Events by
            'source timestamp' has events with 'source timestamp' undefined
            returned last in an arbitrary order.

        * unique type

            If set to ``true``, it determines whether the matched Events will
            contain only one event instance of the same type. With the query
            'order' set to 'descending', only one Event with the greatest
            **timestamp** or **source timestamp** will be matched. Setting the
            'order' to 'ascending' will match the Event with the lowest
            **timestamp** or **source timestamp**.

        * max results

            If set, limits the number of matched Events to this number. Matched
            Events are dependent on the query 'order' the same way as in
            'unique type'.


Server - Server communication
-----------------------------

.. todo::

    define backend engine sync messages


Components
----------

Event Server functionality can be defined by using the following components:

.. uml::

    folder "Component 1" <<Component>> {
        component "Event Client" as Client1
    }

    folder "Component 2" <<Component>> {
        component " Event Client" as Client2
    }

    folder "Event Server" {
        component Communication
        component "Module Engine" as ModuleEngine
        component "Generic Module 1" <<Module>> as Module1
        component "Generic Module 2" <<Module>> as Module2
        component "Specialized Module Engine" <<Module>> as SpecModuleEngine
        component "Specialized Module 1" <<Specialized Module>> as SpecModule1
        component "Specialized Module 2" <<Specialized Module>> as SpecModule2
        component "Backend Engine" as BackendEngine
        component "Backend" as Backend
        component "Backend 1" <<Backend>> as Backend1
        component "Backend 2" <<Backend>> as Backend2

        interface subscribe
        interface notify
        interface register
        interface query
    }

    folder "Remote Event Server" {
        component "Backend Engine" as RemoteBackendEngine
    }

    database "Database 1" <<Database>> as Database1
    database "Database 2" <<Database>> as Database2

    Communication -- subscribe
    Communication -- notify
    Communication -- register
    Communication -- query

    subscribe <-- Client1
    notify --> Client1
    register <-- Client1
    query <-- Client1

    subscribe <-- Client2
    notify --> Client2
    register <-- Client2
    query <-- Client2

    ModuleEngine <-> Communication
    ModuleEngine --> BackendEngine

    Module1 --o ModuleEngine
    Module2 --o ModuleEngine
    SpecModuleEngine --o ModuleEngine
    SpecModule1 --o SpecModuleEngine
    SpecModule2 --o SpecModuleEngine

    BackendEngine o-- Backend
    Backend <|-- Backend1
    Backend <|-- Backend2

    Backend1 --> Database1
    Backend2 --> Database2

    RemoteBackendEngine <--> BackendEngine


Client
''''''

Event client is any component that provides client functionality in
`Server - Client` communication. Package `hat-event` provides python
implementation of `hat.event.client` module which can be used as a basis for
communication with Event Server. This module provides low-level and high-level
communication API. For more detail see documentation of `hat.event.client`
module.


Communication
'''''''''''''

Event Server's communication module is responsible for providing implementation
of server side `Server - Client` communication. This component translates
client requests to module engine's method calls. At the same time, it observes
all new event notifications made by module engine and notifies clients with
appropriate messages.

`RegisterEvent` objects obtained from client's register requests must be
converted to `ProcessEvent` before they can be passed for further processing
to module engine. This conversion is done by module engine, as it is the only
entity responsible for creating new `ProcessEvent` objects.

A unique identifier is assigned to each chatter connection established with
communication (unique for the single execution lifetime of Event Server
process). This identifier is associated with all `ProcessEvent` objects obtained
from corresponding connection.

Communication associates connection with information received as part of
connection's last subscribe message. This subscription is used as a filter for
selecting subset of event notifications which are sent to associated connection.

.. todo::

    add additional system events generated internal by communication (e.g.
    client connected / disconnected)


Module engine
'''''''''''''

Module engine is responsible for creating modules and coordinating event
registration, processing and querying between communication, modules and
backend engine.

Module engine provides method for creating process events utilized by
communication and modules. By creating process events, register events are
enhanced with unique identifier and source identification. Identifier
assigned to process event is the same one that is assigned to corresponding
event. Information regarding source identifier is available only during
processing of process event and is discarded once event is created.

Process of creating events based on a single set of process events is called
session. Module engine starts new session each time communication or module
requests new registration. Session ends once backend engine returns result
of event registration and all modules are notified with this result. Start
and end of each session is notified to each module by creating and closing
module session. Each module instantiates its own module session.

During session processing, each module session is notified with a list of new
and deleted process events which are not previously presented to that module.
Processing these process events by module session can result in new process
events which are to be added to current session or list of previously
added process events which are to be deleted from session. All other module
sessions, except the one that produced list of new and deleted process events,
are notified with those process event lists. This process continues iteratively
until all module sessions return empty lists for both new and deleted process
events. Processing process events by single module session is always sequential
- module session is notified with session changes after its previous
notification processing is finished. Different module sessions may be processed
concurrently. Module engine keeps order of new process events added to session,
but it is allowed to aggregate processing results from multiple module sessions
into a single session change notification.

Care should be taken by module implementation not to cause self recursive or
mutually recursive endless processing loop.

Each module can define its event type filter condition which is used for
filtering new and deleted process events that will get notified to module
session. When session finishes, module session is closed by calling its
`async_close` method, which receives a list of all newly created events
resulting from the session processing. These events are not filtered by module
subscription. By calling `async_close` with list of all newly registered
events, module engine provides each module session with opportunity to
post-process single session as a whole.

.. todo::

    do we want to filter resulting events passed to module session close
    with module's subscription?


Modules
'''''''

.. warning::

    Event server does not provide sandbox environment for loading end executing
    modules. Modules have full access to Event Server functionality which
    is controlled with module execution. Module implementation and
    configuration should be written in accordance to other modules and
    Event Server as a whole, keeping in mind processing execution time overhead
    and possible interference between modules.

Each module represents predefined and configurable closely related functions
that can modify the process of registering new events or initiate new event
registration sessions. When created, module is provided with reference to
module engine which can be used for creating new process events, registering
process events and querying events. Responsibility of each module, upon
creation, is to create its own source identifier which will be unique for
single Event Server process execution.

Modules available as part of `hat-event` package:

    .. toctree::
       :maxdepth: 1

       modules/dummy


Backend engine
''''''''''''''

Backend engine is responsible for actions involving persisting process events
and querying events. During initialization, backend engine creates a single
instance of backend which is used for storage.

During registration of events, backend engine converts process events to
backend events. This conversion involves setting event's timestamp (which is
the same for all events registered in a single session) and replacing
event type with event type identifier. To enable this, backend engine
has to maintain association reference between event types and corresponding
event type identifiers. By replacing event types with identifiers, list of
strings which represent event type is replaced with a single numeric identifier.

Query request which is passed to backend engine contains event types as
optional filter condition. Responsibility of backend engine is to find
all matching event type identifiers and query backend based on a list of
identifiers.

.. todo::

    can we associate type identifiers based on subtypes and utilize identifier
    ranges instead of explicitly passing each identifier to backend

.. todo::

    sync between backend engines


Backends
''''''''

Backends are simple wrappers for storing and retrieving events from specialized
storage engines.

Backends available as part of `hat-event` package:

    .. toctree::
       :maxdepth: 1

       backends/dummy
       backends/sqlite


Python implementation
---------------------

Common
''''''

.. automodule:: hat.event.common


Client
''''''

.. automodule:: hat.event.client


Server
''''''

.. automodule:: hat.event.server.common

.. automodule:: hat.event.server.communication

.. automodule:: hat.event.server.module_engine

.. automodule:: hat.event.server.backend_engine
