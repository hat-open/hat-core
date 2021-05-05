Hat Core - Statechart library
=============================

This library is part of Hat Open project - open-source framework of tools and
libraries for developing applications used for remote monitoring, control and
management of intelligent electronic devices such as IoT devices, PLCs,
industrial automation or home automation systems.

Development of Hat Open and associated repositories is sponsored by
Končar - Power Plant and Electric Traction Engineering Inc.
(Končar KET - `<https://www.koncar-ket.hr>`_).

For more information see:

    * `hat-stc` documentation - `<https://core.hat-open.com/docs/libraries/stc/index.html>`_
    * Hat Core homepage - `<https://core.hat-open.com>`_
    * Hat Core git repository - `<https://github.com/hat-open/hat-core.git>`_

.. warning::

    This project is currently in state of active development. Features,
    functionality and API are unstable.


About
-----

Hierarchical state machine library with support for SCXML and Graphviz
visualization::

    EventName = str
    """Event name"""

    StateName = str
    """State name"""

    ActionName = str
    """Action name"""

    ConditionName = str
    """Condition name"""

    class Event(typing.NamedTuple):
        name: EventName
        payload: typing.Any = None

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

    Action = typing.Callable[['Statechart', typing.Optional[Event]], None]
    """Action function"""

    Condition = typing.Callable[['Statechart', typing.Optional[Event]], bool]
    """Condition function"""

    class Statechart:
        """Statechart engine"""

        def __init__(self,
                     states: typing.Iterable[State],
                     actions: typing.Dict[str, Action],
                     conditions: typing.Dict[str, Condition] = {}): ...

        @property
        def state(self) -> typing.Optional[StateName]:
            """Current state"""

        def register(self, event: Event):
            """Add event to queue"""

        async def run(self):
            """Run statechart"""

    def parse_scxml(scxml: typing.Union[typing.TextIO, pathlib.Path]
                    ) -> typing.List[State]:
        """Parse SCXML"""


    def create_dot_graph(states: typing.Iterable[State]) -> str:
        """Create DOT representation of statechart"""
