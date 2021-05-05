LMDB backend
============

LMDB backend utilizes python `lmdb package <https://pypi.org/project/lmdb/>`_
wrapper for `LMDB data store <https://symas.com/lmdb/>`_.

This backend provides following characteristics:

    * storage of all event structures
    * querying by all query data parameters
    * optimization for latest events querying
    * optimization for time series querying
    * fragmentation of time series entries based on event types
    * in memory caching of event registration with periodic disk persistence
    * configurable condition rules for filtering event by their content


Storage models
--------------

Storage of events in LMDB backend is based on two models:

    * key-value storage
    * time series storage


Key-value storage
'''''''''''''''''

Key-value storage is used as storage model for persisting latest events for
each event type. Configuration provides parameter defining which events,
based on their event type, are stored in key-value store. During backend
initialization, content of whole key-value storage is loaded in memory and
continuously updated with new event registrations. This enables quick access
to event data without need for disk read operations during query executions.


Time series storage
'''''''''''''''''''

Time series storage provide storage model where all events are orderly stored
based on their event timestamp or event source timestamp. Configuration enables
definition of multiple sets defined by event types. For each configured set,
two independent time series storages are created - one based on event timestamp
and other based on event source timestamp. This fragmentation of stored events
into independent time series enables fine tuning and optimizations based on
expected query types. For general cases, usage of single set of configured
event types, which includes all event that should be persisted, is suggested.
Events without source timestamp are stored only in storage based on event
timestamp. Querying of events is based on sequential checking of query
conditions which occurred in time segments constrained by query data.


Event filtering
---------------

During registration and event querying, this backend discards all event
occurrences which do not satisfy configured conditions. Conditions are defined
and applied based on event type. These conditions provide plausibility of
condition composition (by operators `all` and `any`) and testing based on event
content.


Query planning
--------------

During event querying, simple query planning is done based on following steps:

    * if query data filters only latest events for each queried event type,
      then only key-value storage is searched for possible event instances

    * for all other queries, time series partition is searched, in order
      as they are defined in configuration, for first series that contains
      at least one possible event type constrained by query data - only that
      time series storage partition is used as source of event instances
      returned by query

    * if no time series storage could be found, empty list is returned as query
      result


Disk persisting
---------------

Registration of new events for both storage models, doesn't initiate immediate
disk writes. All changes are cached in memory and periodically written
to disk as part of single transaction which includes all storages. This
period is defined by configuration. Writing of memory cache is also part of
backend's standard closing procedure. Single transaction responsible for
writing all memory caches to disk also include cleanup operation which enabled
deletion of oldest entries in time series storages. Each time series storage
can have its own configuration defined limit which specifies event
persistent period based on event timestamp or event source timestamp.


Limiting time series size
-------------------------

Each time series storage can optionally limit number of stored events. This
functionality is associated with disk persisting procedure and is part
of same database transaction. Supported limits include:

    * `min_entries`

        Minimum number of events preserved in database despite of other
        limits. This property can be used as "low water mark" - number
        of entries always available.

    * `max_entries`

        Maximum number of event preserver in database. This property can be
        used as "high water mark" - number of entries will never exceed this
        number.

    * `duration`

        Time in seconds representing maximum duration between current time
        and time used as time series key. All entries which exceed this
        duration will be removed.

    * `size`

        Size in bytes allocated for associated time series. Once time series
        exceeds this storage size, some of the oldest entries are removed.
        Number of removed entries is calculated based on average entry size
        and limiting storage size.
