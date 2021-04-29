.. _hat-stc:

`hat.stc` - Python statechart library
=====================================

This library provides basic implementation of
`hierarchical state machine <https://en.wikipedia.org/wiki/UML_state_machine>`_
engine. Statechart definition can be provided as structures defined by API or
by `SCXML definition <https://www.w3.org/TR/scxml/>`_. Additionally,
`Graphviz <https://graphviz.org/>`_ DOT graph can be generated based on state
definition together with Sphinx extension `hat.sphinx.scxml`.

Notable differences between `hat.stc` and SCXML standard:

    * initial child state (in `scxml` and `state` tag) should be defined
      only by setting parent's `initial` attribute

    * transitions without associated event name are not supported

    * parallel substates are not supported

    * history pseudo-state is not supported

    * data model is not supported

    * external communications is not supported

    * all actions and conditions are identified by name - arbitrary expressions
      or executable contents are not supported

    * transition event identifiers are used as exact event names without
      support for substring segmentation matching


Tutorial
--------

Hierarchical state machines (also known as statecharts) are abstractions
used as organization/implementation basis for algorithms that execute
continuous state changes. Interaction between "outside world" and statecharts
is usually represented with sequence of events that are directly responsible
for state changes.


Statechart definition
'''''''''''''''''''''

As an example of trivial state machine, let us borrow simple example from
`Wikipedia <https://en.wikipedia.org/wiki/File:Finite_state_machine_example_with_comments.svg>`_:

.. drawio-image:: tutorial.drawio
   :page-index: 0
   :align: center

This diagram models simple door with only two states - `opened` and `closed`.
`Opened` is initial state which can transition to `closed` state once `close`
event occurs. Similarly, once in `closed` state, door can change to `opened`
state if `open` event occurs. Both states have associated entry action (named
`printState`) which is triggered each time state is entered.

The same statechart can be described with following SCXML definition::

    <?xml version="1.0" encoding="UTF-8"?>
    <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="opened" version="1.0">
        <state id="opened">
            <onentry>printState</onentry>
            <transition event="close" target="closed"/>
        </state>
        <state id="closed">
            <onentry>printState</onentry>
            <transition event="open" target="opened"/>
        </state>
    </scxml>

`hat.stc` library provides function ``hat.stc.parse_scxml`` which can be used
for parsing SCXML definitions into state definitions usable by
``hat.stc.Statechart``. Equivalent definition of this SCXML represented by
``hat.stc.State`` definitions is::

    [State(name='opened',
           transitions=[Transition(event='close', target='closed')],
           entries=['printState']),
     State(name='closed',
           transitions=[Transition(event='open', target='opened')],
           entries=['printState'])]

Both SCXML and `hat.stc.State` based definitions represent identical statechart
definition and it is up to user to chose more appropriate notation for
statechart definitions. In the rest of this tutorial, we will be using
SCXML definitions.


Creating statechart instance
''''''''''''''''''''''''''''

Once we have prepared statechart definition, we can create new instance
of `hat.stc.Statechart`::

    def act_print_state(evt):
        print('current state:', door.state)

    states = parse_scxml("door01.scxml")
    actions = {'printState': act_print_state}
    door = Statechart(states, actions)

During instance initialization, together with state definitions, we provide
action bindings. Action bindings is dictionary which contains all action
names, used in state definitions, associated with regular functions
providing action implementation. In out case, definition contains action
``printState`` (same action is used as entry action for both `opened` and
`closed` state) which is associated with ``act_print_state`` function - simple
function that prints current state of our statechart instance.

By keeping state definition separate from associated actions and statechart
instances, single list of state definitions can be used as blueprint for
creating arbitrary number of mutually independent instances.


Running statechart
''''''''''''''''''

Execution of statechart logic is controlled with execution of
`hat.stc.Statechart.run` coroutine. Once started, statechart will transition
to initial state and wait for registered events that will cause state
transitions::

    run_task = asyncio.create_task(door.run())
    await asyncio.sleep(1)

    print('registering close event')
    door.register(Event('close'))
    await asyncio.sleep(1)

    print('registering open event')
    door.register(Event('open'))
    await asyncio.sleep(1)

    run_task.cancel()

By executing this example, following output can be expected::

    current state: opened
    registering close event
    current state: closed
    registering open event
    current state: opened


Representing statechart as python class
'''''''''''''''''''''''''''''''''''''''

To provide clean interface, we can encapsulate out derived statechart
functionality as single class::

    door_states = parse_scxml(scxml)

    class Door:

        def __init__(self):
            actions = {'printState': self._act_print_state}
            self._stc = Statechart(door_states, actions)
            self._run_task = asyncio.create_task(self._stc.run())

        def close(self):
            print('registering close event')
            self._stc.register(Event('close'))

        def open(self):
            print('registering open event')
            self._stc.register(Event('open'))

        def finish(self):
            self._run_task.cancel()

        def _act_print_state(self, evt):
            print('current state:', self._stc.state)

Now we can instantiate and test our simple door::

    door = Door()
    await asyncio.sleep(1)

    door.close()
    await asyncio.sleep(1)

    door.open()
    await asyncio.sleep(1)

    door.finish()

This execution produces same result as out previous example::

    current state: opened
    registering close event
    current state: closed
    registering open event
    current state: opened


Processing registered events
''''''''''''''''''''''''''''

To help our analysis of event processing, we will introduce "force" to our
operations of door closing and opening. This "force" will be represented
with number in range [`0`, `100`] where `0` represents minimal opening/closing
force and `100` represents maximal opening/closing force.

This enhancement can be represented with following changes to door methods::

    def close(self, force):
        print('registering close event')
        self._stc.register(Event('close', force))

    def open(self):
        print('registering open event')
        self._stc.register(Event('open', force))

    def _act_print_state(self, evt):
        force = evt.payload if evt else 0
        print(f'force {force} caused transition to {self._stc.state}')

Now our test sequence::

    door = Door()
    await asyncio.sleep(1)

    door.close(20)
    await asyncio.sleep(1)

    door.open(50)
    await asyncio.sleep(1)

    door.finish()

results in::

    force None caused transition to opened
    registering close event
    force 20 caused transition to closed
    registering open event
    force 50 caused transition to opened

Each instance of `hat.std.Statechart` has it's own event queue. All registered
events are added to the end of this queue. During execution of
`hat.stc.Statechart.run`, events are taken one at the time from begging of
event queue and checked for possible transitions. When transition is found,
it will cause statechart instance to change it's state and execute all
appropriate actions. If transition paired with event could not be found,
event is discarded and statechart doesn't change it's state. Once all events
from the event queue are processed, `hat.stc.Statechart.run` will wait for
new events to be added to event queue.

Taking this into account, by omitting `asyncio.sleep` calls between
opening/closing doors, we can expect same transitions. Therefore::

    door = Door()
    door.close(20)
    door.open(50)

    await asyncio.sleep(1)
    door.finish()

results in::

    registering close event
    registering open event
    force None caused transition to opened
    force 20 caused transition to closed
    force 50 caused transition to opened

Also, if we try to open already opened door or close already closed door,
this operations will be ignored. Therefore::

    door = Door()
    door.open(10)
    door.close(20)
    door.close(30)
    door.open(40)

    await asyncio.sleep(1)
    door.finish()

results in::

    registering open event
    registering close event
    registering close event
    registering open event
    force None caused transition to opened
    force 20 caused transition to closed
    force 40 caused transition to opened


Working with timeouts
'''''''''''''''''''''

.. todo::

    ...


Composite states
''''''''''''''''

.. todo::

    ...


Advanced transitions
''''''''''''''''''''

.. todo::

    ...


API
---

API reference is available as part of generated documentation:

    * `Python hat.stc module <../../pyhat/hat/stc.html>`_
