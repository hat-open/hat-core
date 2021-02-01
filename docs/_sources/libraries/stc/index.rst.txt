.. _hat-stc:

`hat.stc` - Python statechart library
=====================================

This library provides basic implementation of
`hierarchical state machine <https://en.wikipedia.org/wiki/UML_state_machine>`_
engine. Statechart definition can be provided as structures defined by API or
by `SCXML definition <https://www.w3.org/TR/scxml/>`_. Additionally,
`Graphviz <https://graphviz.org/>`_ DOT graph can be generated based on state
definition.


Statechart definitions
----------------------

Prior to statechart execution, state with all transition definitions are
required::

    EventName = str
    StateName = str
    ActionName = str
    ConditionName = str

    class Transition(typing.NamedTuple):
        event: EventName
        target: typing.Optional[StateName]
        actions: typing.List[ActionName] = []
        conditions: typing.List[ConditionName] = []
        internal: bool = False

    class State(typing.NamedTuple):
        name: StateName
        children: typing.List['State'] = []
        transitions: typing.List[Transition] = []
        entries: typing.List[ActionName] = []
        exits: typing.List[ActionName] = []
        final: bool = False

State is defined by:

    * `name`

        Unique state identifier.

    * `children`

        Optional child states. If state has children, first child is
        considered as its initial state.

    * `transitions`

        Possible transitions to other states.

    * `entries`

        Actions executed when state is entered.

    * `exists`

        Actions executed when state is exited.

    * `final`

        Is state final.

Transition is defined by:

    * `event`

        Event identifier. Occurrence of event with this exact identifier can
        trigger state transition.

    * `target`

        Destination state identifier. If destination state is not defined,
        local transition is assumed - state is not changed and transition
        actions are triggered.

    * `conditions`

        List of conditions. Transition is triggered only if all provided
        conditions are met.

    * `internal`

        Internal transition modifier. Determines whether the source state is
        exited in transitions whose target state is a descendant of the source
        state.


Importing SCXML
----------------

State definitions can be created based on SCXML definitions::

    def parse_scxml(scxml: typing.Union[typing.TextIO, pathlib.Path]
                    ) -> typing.List[State]: ...

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


Running statechart
------------------

Statechart instance is represented with instance of `hat.stc.Statechart`
class::

    Action = typing.Callable[[typing.Optional[Event]], None]

    Condition = typing.Callable[[typing.Optional[Event]], bool]

    class Event(typing.NamedTuple):
        name: EventName
        payload: typing.Any = None

    class Statechart:

        def __init__(self,
                     states: typing.Iterable[State],
                     actions: typing.Dict[str, Action],
                     conditions: typing.Dict[str, Condition] = {}): ...

        @property
        def state(self) -> typing.Optional[StateName]: ...

        def register(self, event: Event): ...

        async def run(self): ...

Each instance is initialized with state definitions (first state is considered
initial) and action and condition definitions. Statechart execution is
simulated by calling `run` coroutine. When this coroutine is called,
statechart will transition to initial state and wait for new event occurrences.
New events are registered with `register` method which accepts event instances
containing event name and optional event payload. All event registrations are
queued and processed sequentially. Coroutine `run` continues execution until
statechart transitions to final state. Once final state is reached, `run`
finishes execution. During statechart execution, actions and conditions
are called based on state changes and associated transitions provided during
initialization. Condition is considered met only if result of calling
condition function is ``True``.


Visualization
-------------

`hat.stc` provides function for generating Graphviz DOT graph definitions
based on state definitions (which can be obtained by importing SCXML)::

    def create_dot_graph(states: typing.Iterable[State]) -> str: ...

Sphinx extension `hat.sphinx.scxml` can be used for generating statechart
definition visualization.


Example
-------

.. scxml:: example.scxml

::

        states = stc.parse_scxml(io.StringIO(r"""<?xml version="1.0" encoding="UTF-8"?>
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="on" version="1.0">
            <state id="on" initial="operand1">
                <onentry>clear</onentry>
                <transition event="C" target="on"/>
                <transition event="OFF" target="off"/>
                <state id="operand1">
                    <transition event="number" target="operand1">appendOperand1</transition>
                    <transition event="operator" target="opEntered"/>
                </state>
                <state id="opEntered">
                    <onentry>setOperator</onentry>
                    <transition event="number" target="operand2">setOperand2</transition>
                </state>
                <state id="operand2">
                    <transition event="number" target="operand2">appendOperand2</transition>
                    <transition event="equals" target="result"/>
                </state>
                <state id="result">
                    <onentry>calculate</onentry>
                    <transition event="number" target="operand1">setOperand1</transition>
                    <transition event="operator" target="opEntered">resultAsOperand1</transition>
                </state>
            </state>
            <final id="off"/>
        </scxml>"""))  # NOQA

    class Calculator:

        def __init__(self):
            actions = {'clear': self._act_clear,
                       'setOperand1': self._act_setOperand1,
                       'appendOperand1': self._act_appendOperand1,
                       'setOperand2': self._act_setOperand2,
                       'appendOperand2': self._act_appendOperand2,
                       'resultAsOperand1': self._act_resultAsOperand1,
                       'setOperator': self._act_setOperator,
                       'calculate': self._act_calculate}
            self._operand1 = None
            self._operand2 = None
            self._operator = None
            self._result = None
            self._machine = stc.Statechart(states, actions)

        @property
        def result(self):
            return self._result

        def push_number(self, number):
            self._machine.register(stc.Event('number', number))

        def push_operator(self, operator):
            self._machine.register(stc.Event('operator', operator))

        def push_equals(self):
            self._machine.register(stc.Event('equals'))

        def push_C(self):
            self._machine.register(stc.Event('C'))

        def push_OFF(self):
            self._machine.register(stc.Event('OFF'))

        async def run(self):
            await self._machine.run()

        def _act_clear(self, evt):
            self._operand1 = 0
            self._operand2 = 0
            self._operator = None
            self._result = 0

        def _act_setOperand1(self, evt):
            self._operand1 = evt.payload

        def _act_appendOperand1(self, evt):
            self._operand1 = self._operand1 * 10 + evt.payload

        def _act_setOperand2(self, evt):
            self._operand2 = evt.payload

        def _act_appendOperand2(self, evt):
            self._operand2 = self._operand2 * 10 + evt.payload

        def _act_resultAsOperand1(self, evt):
            self._operand1 = self._result

        def _act_setOperator(self, evt):
            self._operator = evt.payload

        def _act_calculate(self, evt):
            if self._operator == '+':
                self._result = self._operand1 + self._operand2
            elif self._operator == '-':
                self._result = self._operand1 - self._operand2
            elif self._operator == '*':
                self._result = self._operand1 * self._operand2
            elif self._operator == '/':
                self._result = self._operand1 / self._operand2
            else:
                raise Exception('invalid operator')

    calc = Calculator()
    calc.push_number(1)
    calc.push_number(2)
    calc.push_number(3)
    calc.push_operator('*')
    calc.push_number(2)
    calc.push_equals()
    calc.push_OFF()
    await calc.run()
    assert calc.result == 246


API
---

API reference is available as part of generated documentation:

    * `Python hat.stc module <../pyhat/hat/stc.html>`_
