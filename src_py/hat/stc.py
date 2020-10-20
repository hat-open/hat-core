"""Statechart module"""

import collections
import itertools
import pathlib
import typing
import xml.etree.ElementTree

from hat.util import aio


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


Action = typing.Callable[[typing.Optional[Event]], None]
"""Action function"""

Condition = typing.Callable[[typing.Optional[Event]], bool]
"""Condition function"""


class Statechart:
    """Statechart engine"""

    def __init__(self,
                 states: typing.Iterable[State],
                 actions: typing.Dict[str, Action],
                 conditions: typing.Dict[str, Condition] = {}):
        states = collections.deque(states)

        self._initial = states[0].name if states else None
        self._actions = actions
        self._conditions = conditions
        self._states = {}
        self._parents = {}
        self._stack = collections.deque()
        self._queue = aio.Queue()

        while states:
            state = states.pop()
            states.extend(state.children)
            self._states[state.name] = state
            self._parents.update({i.name: state.name for i in state.children})

    @property
    def state(self) -> typing.Optional[StateName]:
        """Current state"""
        return self._stack[-1] if self._stack else None

    def register(self, event: Event):
        """Add event to queue"""
        self._queue.put_nowait(event)

    async def run(self):
        """Run statechart"""
        self._walk_up(None, None)
        self._walk_down(self._initial, None)
        while True:
            state = self.state
            if not state or self._states[state].final:
                break
            event = await self._queue.get()
            state, transition = self._find_state_transition(state, event)
            if not transition:
                continue
            if transition.target:
                ancestor = self._find_ancestor(state, transition.target,
                                               transition.internal)
                self._walk_up(ancestor, event)
            self._exec_actions(transition.actions, event)
            if transition.target:
                self._walk_down(transition.target, event)

    def _walk_up(self, target, event):
        while self.state != target:
            state = self._states[self.state]
            self._exec_actions(state.exits, event)
            self._stack.pop()

    def _walk_down(self, target, event):
        target = target or self._initial
        if not target:
            return
        states = collections.deque([self._states[target]])
        while ((state := states[0]).name != self.state and
                (parent := self._parents.get(state.name))):
            states.appendleft(self._states[parent])
        while (state := states[-1]).children:
            states.append(state.children[0])
        if states[0].name == self.state:
            states.popleft()
        for state in states:
            self._stack.append(state.name)
            self._exec_actions(state.entries, event)

    def _find_state_transition(self, state, event):
        while state:
            for transition in self._states[state].transitions:
                if transition.event != event.name:
                    continue
                if not all(self._conditions[condition](event)
                           for condition in transition.conditions):
                    continue
                return state, transition
            state = self._parents.get(state)
        return None, None

    def _find_ancestor(self, state, sibling, internal):
        if not sibling or not state:
            return
        path = collections.deque([sibling])
        while (parent := self._parents.get(path[0])):
            path.appendleft(parent)
        ancestor = None
        for i, j in zip(self._stack, path):
            if i != j:
                break
            if i in [sibling, state]:
                if internal and i == state:
                    ancestor = i
                break
            ancestor = i
        return ancestor

    def _exec_actions(self, names, event):
        for name in names:
            action = self._actions[name]
            action(event)


def parse_scxml(scxml: typing.Union[typing.TextIO, pathlib.Path]
                ) -> typing.List[State]:
    """Parse SCXML"""
    if isinstance(scxml, pathlib.Path):
        with open(scxml, encoding='utf-8') as f:
            root_el = _read_xml(f)
    else:
        root_el = _read_xml(scxml)
    return _parse_scxml_states(root_el)


def _parse_scxml_states(parent_el):
    states = {}
    for state_el in itertools.chain(parent_el.findall("./state"),
                                    parent_el.findall("./final")):
        state = _parse_scxml_state(state_el)
        states[state.name] = state
    if not states:
        return []
    initial = parent_el.get('initial')
    return [states[initial], *(state for name, state in states.items()
                               if name != initial)]


def _parse_scxml_state(state_el):
    return State(name=state_el.get('id'),
                 children=_parse_scxml_states(state_el),
                 transitions=[_parse_scxml_transition(i)
                              for i in state_el.findall('./transition')],
                 entries=[entry_el.text
                          for entry_el in state_el.findall('./onentry')
                          if entry_el.text],
                 exits=[exit_el.text
                        for exit_el in state_el.findall('./onexit')
                        if exit_el.text],
                 final=state_el.tag == 'final')


def _parse_scxml_transition(transition_el):
    return Transition(event=transition_el.get('event'),
                      target=transition_el.get('target'),
                      actions=[i
                               for i in (transition_el.text or '').split(' ')
                               if i],
                      conditions=[i for i in (transition_el.get('cond') or
                                              '').split(' ')
                                  if i],
                      internal=transition_el.get('type') == 'internal')


def _read_xml(source):
    it = xml.etree.ElementTree.iterparse(source)
    for _, el in it:
        prefix, has_namespace, postfix = el.tag.partition('}')
        if has_namespace:
            el.tag = postfix
    return it.root
