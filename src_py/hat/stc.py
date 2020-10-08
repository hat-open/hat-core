"""Statechart module"""

import collections
import typing
import xml.etree.ElementTree

from hat.util import aio


EventName = str
StateName = str
ActionName = str


class Event(typing.NamedTuple):
    name: EventName
    payload: typing.Any = None


class Transition(typing.NamedTuple):
    event: EventName
    destination: StateName
    action: typing.Optional[ActionName] = None
    local: bool = False


class State(typing.NamedTuple):
    name: StateName
    children: typing.List['State'] = []
    transitions: typing.List[Transition] = []
    entry: typing.Optional[ActionName] = None
    exit: typing.Optional[ActionName] = None


Action = typing.Callable[['Statechart', typing.Optional[Event]], None]


class Statechart:

    def __init__(self,
                 states: typing.Iterable[State],
                 actions: typing.Dict[str, Action]):
        states = collections.deque(states)

        self._initial = states[0].name if states else None
        self._actions = actions
        self._states = {}
        self._parents = {}
        self._transitions = {}
        self._stack = collections.deque()
        self._queue = aio.Queue()

        while states:
            state = states.pop()
            states.extend(state.children)
            self._states[state.name] = state
            self._parents.update({i.name: state.name for i in state.children})
            if state.name not in self._parents:
                self._parents[state.name] = None
            for transition in state.transitions:
                self._transitions[(state.name, transition.event)] = transition

    @property
    def state(self) -> typing.Optional[StateName]:
        """Current state"""
        return self._stack[-1] if self._stack else None

    def register(self, event: Event):
        """Add event to queue"""
        self._queue.put_nowait(event)

    async def run(self):
        """Run statechart"""
        transition = Transition(None, self._initial)
        self._walk(None, transition, None)
        async for event in self._queue:
            state = self.state
            transition = None
            while state:
                transition = self._transitions.get((state, event.name))
                if transition:
                    break
                state = self._parents[state]
            if transition:
                ancestor = self._find_ancestor(state, transition.destination,
                                               transition.local)
                self._walk(ancestor, transition, event)

    def _walk(self, ancestor, transition, event):
        self._walk_up(ancestor, event)
        self._exec_action(transition.action, event)
        self._walk_down(transition.destination, event)

    def _walk_up(self, destination, event):
        while self.state != destination:
            state = self._states[self.state]
            self._exec_action(state.exit, event)
            self._stack.pop()

    def _walk_down(self, destination, event):
        destination = destination or self._initial
        if not destination:
            return
        states = collections.deque([self._states[destination]])
        while ((state := states[0]).name != self.state and
                (parent := self._parents[state.name])):
            states.appendleft(self._states[parent])
        while (state := states[-1]).children:
            states.append(state.children[0])
        if states[0].name == self.state:
            states.popleft()
        for state in states:
            self._stack.append(state.name)
            self._exec_action(state.entry, event)

    def _find_ancestor(self, state, sibling, local):
        if not sibling or not state:
            return
        path = collections.deque([sibling])
        while (parent := self._parents[path[0]]):
            path.appendleft(parent)
        ancestor = None
        for i, j in zip(self._stack, path):
            if i != j:
                break
            if not local and i in [sibling, state]:
                break
            ancestor = i
            if i == state:
                break
        return ancestor

    def _exec_action(self, name, event):
        if not name:
            return
        action = self._actions[name]
        action(self, event)


def parse_scxml(scxml: typing.TextIO) -> typing.List[State]:
    """Parse SCXML"""
    root_el = _read_xml(scxml)
    return _parse_scxml_states(root_el)


def _parse_scxml_states(parent_el):
    states = {}
    for state_el in parent_el.findall("./state"):
        state = _parse_scxml_state(state_el)
        states[state.name] = state
    if not states:
        return []
    initial = parent_el.get('initial')
    return [states[initial], *(state for name, state in states.items()
                               if name != initial)]


def _parse_scxml_state(state_el):
    entry_el = state_el.find('./onentry')
    exit_el = state_el.find('./onexit')
    entry = (entry_el.text or None) if entry_el is not None else None
    exit = (exit_el.text or None) if exit_el is not None else None
    return State(name=state_el.get('id'),
                 children=_parse_scxml_states(state_el),
                 transitions=[_parse_scxml_transition(i)
                              for i in state_el.findall('./transition')],
                 entry=entry,
                 exit=exit)


def _parse_scxml_transition(transition_el):
    return Transition(event=transition_el.get('event'),
                      destination=transition_el.get('target'),
                      action=transition_el.text or None,
                      local=transition_el.get('type') == 'internal')


def _read_xml(source):
    it = xml.etree.ElementTree.iterparse(source)
    for _, el in it:
        prefix, has_namespace, postfix = el.tag.partition('}')
        if has_namespace:
            el.tag = postfix
    return it.root
