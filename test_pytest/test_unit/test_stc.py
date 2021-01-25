import asyncio
import io

import pytest

from hat import aio
from hat import stc


pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("scxml, states", [
    (r"""<?xml version="1.0" encoding="UTF-8"?>
        <scxml xmlns="http://www.w3.org/2005/07/scxml" version="1.0">
        </scxml>""",  # NOQA
     []),

    (r"""<?xml version="1.0" encoding="UTF-8"?>
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1" version="1.0">
        <state id="s1"/>
        </scxml>""",  # NOQA
     [stc.State('s1')]),

    (r"""<?xml version="1.0" encoding="UTF-8"?>
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s2" version="1.0">
        <state id="s1"/>
        <state id="s2"/>
        <state id="s3"/>
        </scxml>""",  # NOQA
     [stc.State('s2'),
      stc.State('s1'),
      stc.State('s3')]),

    (r"""<?xml version="1.0" encoding="UTF-8"?>
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1" version="1.0">
        <state id="s1">
            <transition event="e1" target="s2"/>
            <transition event="e2" target="s1">a1</transition>
        </state>
        <state id="s2">
            <transition event="e3" target="s2" type="internal"/>
        </state>
        </scxml>""",  # NOQA
     [stc.State('s1',
                transitions=[stc.Transition('e1', 's2'),
                             stc.Transition('e2', 's1', actions=['a1'])]),
      stc.State('s2',
                transitions=[stc.Transition('e3', 's2', internal=True)])]),

    (r"""<?xml version="1.0" encoding="UTF-8"?>
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1" version="1.0">
        <state id="s1" initial="s2">
            <onentry>a1</onentry>
            <state id="s2">
                <onexit>a2</onexit>
            </state>
        </state>
        <state id="s3">
            <onentry>a3</onentry>
            <onexit>a4</onexit>
        </state>
        </scxml>""",  # NOQA
     [stc.State('s1',
                entries=['a1'],
                children=[stc.State('s2', exits=['a2'])]),
      stc.State('s3',
                entries=['a3'],
                exits=['a4'])]),

    (r"""<?xml version="1.0" encoding="UTF-8"?>
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1" version="1.0">
        <state id="s1">
            <transition event="e1"/>
            <transition event="e2" cond="c1"/>
            <transition event="e2" cond="c2 c3"/>
        </state>
        </scxml>""",  # NOQA
     [stc.State('s1',
                transitions=[stc.Transition('e1', None),
                             stc.Transition('e2', None,
                                            conditions=['c1']),
                             stc.Transition('e2', None,
                                            conditions=['c2', 'c3'])])]),

])
def test_parse_scxml(scxml, states):
    result = stc.parse_scxml(io.StringIO(scxml))
    assert result == states


async def test_empty():
    machine = stc.Statechart([], {})
    assert machine.state is None
    await asyncio.wait_for(machine.run(), 0.01)


async def test_single_state():
    queue = aio.Queue()
    states = [stc.State('s1',
                        transitions=[
                            stc.Transition('e1', 's1', ['transit']),
                            stc.Transition('e2', 's1', ['transit'], [], True)],
                        entries=['enter'],
                        exits=['exit'])]
    actions = {'enter': lambda e: queue.put_nowait(('enter', e)),
               'exit': lambda e: queue.put_nowait(('exit', e)),
               'transit': lambda e: queue.put_nowait(('transit', e))}
    machine = stc.Statechart(states, actions)
    assert machine.state is None

    f = asyncio.ensure_future(machine.run())
    a, e = await queue.get()
    assert a == 'enter'
    assert e is None
    assert machine.state == 's1'

    await asyncio.sleep(0.001)
    assert queue.empty()

    event = stc.Event('e1', None)
    machine.register(event)
    a, e = await queue.get()
    assert (a, e) == ('exit', event)
    a, e = await queue.get()
    assert (a, e) == ('transit', event)
    a, e = await queue.get()
    assert (a, e) == ('enter', event)
    assert machine.state == 's1'

    await asyncio.sleep(0.001)
    assert queue.empty()

    event = stc.Event('e2', 123)
    machine.register(event)
    a, e = await queue.get()
    assert (a, e) == ('transit', event)
    assert machine.state == 's1'

    await asyncio.sleep(0.001)
    assert queue.empty()

    event = stc.Event('e3', None)
    machine.register(event)
    assert machine.state == 's1'

    await asyncio.sleep(0.001)
    assert queue.empty()

    f.cancel()
    with pytest.raises(asyncio.CancelledError):
        await f


async def test_nested_states():
    queue = aio.Queue()
    states = [stc.State(
        's1',
        children=[
            stc.State(
                's2',
                children=[
                    stc.State(
                        's3',
                        transitions=[stc.Transition('e1', 's4', ['transit1'])],
                        entries=['enter_s3'],
                        exits=['exit_s3']),
                    stc.State(
                        's4',
                        entries=['enter_s4'],
                        exits=['exit_s4'])],
                entries=['enter_s2'],
                exits=['exit_s2'])],
        transitions=[stc.Transition('e2', 's2', ['transit2'])],
        entries=['enter_s1'],
        exits=['exit_s1'])]
    actions = {'enter_s1': lambda e: queue.put_nowait(('enter_s1', e)),
               'exit_s1': lambda e: queue.put_nowait(('exit_s1', e)),
               'enter_s2': lambda e: queue.put_nowait(('enter_s2', e)),
               'exit_s2': lambda e: queue.put_nowait(('exit_s2', e)),
               'enter_s3': lambda e: queue.put_nowait(('enter_s3', e)),
               'exit_s3': lambda e: queue.put_nowait(('exit_s3', e)),
               'enter_s4': lambda e: queue.put_nowait(('enter_s4', e)),
               'exit_s4': lambda e: queue.put_nowait(('exit_s4', e)),
               'transit1': lambda e: queue.put_nowait(('transit1', e)),
               'transit2': lambda e: queue.put_nowait(('transit2', e))}
    machine = stc.Statechart(states, actions)
    assert machine.state is None

    f = asyncio.ensure_future(machine.run())
    a, e = await queue.get()
    assert (a, e) == ('enter_s1', None)
    a, e = await queue.get()
    assert (a, e) == ('enter_s2', None)
    a, e = await queue.get()
    assert (a, e) == ('enter_s3', None)
    assert machine.state == 's3'

    await asyncio.sleep(0.001)
    assert queue.empty()

    event = stc.Event('e1', 123)
    machine.register(event)
    a, e = await queue.get()
    assert (a, e) == ('exit_s3', event)
    a, e = await queue.get()
    assert (a, e) == ('transit1', event)
    a, e = await queue.get()
    assert (a, e) == ('enter_s4', event)
    assert machine.state == 's4'

    await asyncio.sleep(0.001)
    assert queue.empty()

    event = stc.Event('e2', 123)
    machine.register(event)
    a, e = await queue.get()
    assert (a, e) == ('exit_s4', event)
    a, e = await queue.get()
    assert (a, e) == ('exit_s2', event)
    a, e = await queue.get()
    assert (a, e) == ('exit_s1', event)
    a, e = await queue.get()
    assert (a, e) == ('transit2', event)
    a, e = await queue.get()
    assert (a, e) == ('enter_s1', event)
    a, e = await queue.get()
    assert (a, e) == ('enter_s2', event)
    a, e = await queue.get()
    assert (a, e) == ('enter_s3', event)
    assert machine.state == 's3'

    f.cancel()
    with pytest.raises(asyncio.CancelledError):
        await f


async def test_conditions():
    queue = aio.Queue()
    states = [stc.State(
        's1',
        transitions=[
            stc.Transition('e', 's1', conditions=['c1'], actions=['a1']),
            stc.Transition('e', 's1', conditions=['c2'], actions=['a2'])])]
    conditions = {'c1': lambda e: e.payload == 1,
                  'c2': lambda e: e.payload == 2}
    actions = {'a1': lambda e: queue.put_nowait('a1'),
               'a2': lambda e: queue.put_nowait('a2')}

    machine = stc.Statechart(states, actions, conditions)
    f = asyncio.ensure_future(machine.run())

    await asyncio.sleep(0.001)
    assert queue.empty()

    event = stc.Event('e', 1)
    machine.register(event)
    a = await queue.get()
    assert a == 'a1'

    await asyncio.sleep(0.001)
    assert queue.empty()

    event = stc.Event('e', 2)
    machine.register(event)
    a = await queue.get()
    assert a == 'a2'

    await asyncio.sleep(0.001)
    assert queue.empty()

    event = stc.Event('e', 3)
    machine.register(event)

    await asyncio.sleep(0.001)
    assert queue.empty()

    f.cancel()
    with pytest.raises(asyncio.CancelledError):
        await f


async def test_local_transitions():
    queue = aio.Queue()
    states = [stc.State(
        's1',
        entries=['enter'],
        transitions=[
            stc.Transition('e1', 's1', actions=['a1']),
            stc.Transition('e2', None, actions=['a2'])])]
    actions = {'enter': lambda e: queue.put_nowait('enter'),
               'a1': lambda e: queue.put_nowait('a1'),
               'a2': lambda e: queue.put_nowait('a2')}

    machine = stc.Statechart(states, actions)
    f = asyncio.ensure_future(machine.run())
    a = await queue.get()
    assert a == 'enter'

    await asyncio.sleep(0.001)
    assert queue.empty()

    event = stc.Event('e1')
    machine.register(event)
    a = await queue.get()
    assert a == 'a1'
    a = await queue.get()
    assert a == 'enter'

    await asyncio.sleep(0.001)
    assert queue.empty()

    event = stc.Event('e2')
    machine.register(event)
    a = await queue.get()
    assert a == 'a2'

    await asyncio.sleep(0.001)
    assert queue.empty()

    f.cancel()
    with pytest.raises(asyncio.CancelledError):
        await f


async def test_example_docs():

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
