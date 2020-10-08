import asyncio
import io

import pytest

from hat import stc
from hat.util import aio


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
                             stc.Transition('e2', 's1', action='a1')]),
      stc.State('s2',
                transitions=[stc.Transition('e3', 's2', local=True)])]),

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
                entry='a1',
                children=[stc.State('s2', exit='a2')]),
      stc.State('s3',
                entry='a3',
                exit='a4')])

])
def test_parse_scxml(scxml, states):
    result = stc.parse_scxml(io.StringIO(scxml))
    assert result == states


async def test_empty():
    machine = stc.Statechart([], {})
    assert machine.state is None

    f = asyncio.ensure_future(machine.run())
    await asyncio.sleep(0.001)
    assert machine.state is None

    machine.register(stc.Event('evt', None))
    await asyncio.sleep(0.001)
    assert machine.state is None

    f.cancel()
    with pytest.raises(asyncio.CancelledError):
        await f


async def test_single_state():
    queue = aio.Queue()
    states = [stc.State('s1',
                        transitions=[
                            stc.Transition('e1', 's1', 'transit'),
                            stc.Transition('e2', 's1', 'transit', True)],
                        entry='enter',
                        exit='exit')]
    actions = {'enter': lambda m, e: queue.put_nowait(('enter', m, e)),
               'exit': lambda m, e: queue.put_nowait(('exit', m, e)),
               'transit': lambda m, e: queue.put_nowait(('transit', m, e))}
    machine = stc.Statechart(states, actions)
    assert machine.state is None

    f = asyncio.ensure_future(machine.run())
    a, m, e = await queue.get()
    assert a == 'enter'
    assert m is machine
    assert e is None
    assert machine.state == 's1'

    await asyncio.sleep(0.001)
    assert queue.empty()

    event = stc.Event('e1', None)
    machine.register(event)
    a, m, e = await queue.get()
    assert (a, m, e) == ('exit', machine, event)
    a, m, e = await queue.get()
    assert (a, m, e) == ('transit', machine, event)
    a, m, e = await queue.get()
    assert (a, m, e) == ('enter', machine, event)
    assert machine.state == 's1'

    await asyncio.sleep(0.001)
    assert queue.empty()

    event = stc.Event('e2', 123)
    machine.register(event)
    a, m, e = await queue.get()
    assert (a, m, e) == ('transit', machine, event)
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
                        transitions=[stc.Transition('e1', 's4', 'transit1')],
                        entry='enter_s3',
                        exit='exit_s3'),
                    stc.State(
                        's4',
                        entry='enter_s4',
                        exit='exit_s4')],
                entry='enter_s2',
                exit='exit_s2')],
        transitions=[stc.Transition('e2', 's2', 'transit2')],
        entry='enter_s1',
        exit='exit_s1')]
    actions = {'enter_s1': lambda m, e: queue.put_nowait(('enter_s1', m, e)),
               'exit_s1': lambda m, e: queue.put_nowait(('exit_s1', m, e)),
               'enter_s2': lambda m, e: queue.put_nowait(('enter_s2', m, e)),
               'exit_s2': lambda m, e: queue.put_nowait(('exit_s2', m, e)),
               'enter_s3': lambda m, e: queue.put_nowait(('enter_s3', m, e)),
               'exit_s3': lambda m, e: queue.put_nowait(('exit_s3', m, e)),
               'enter_s4': lambda m, e: queue.put_nowait(('enter_s4', m, e)),
               'exit_s4': lambda m, e: queue.put_nowait(('exit_s4', m, e)),
               'transit1': lambda m, e: queue.put_nowait(('transit1', m, e)),
               'transit2': lambda m, e: queue.put_nowait(('transit2', m, e))}
    machine = stc.Statechart(states, actions)
    assert machine.state is None

    f = asyncio.ensure_future(machine.run())
    a, m, e = await queue.get()
    assert (a, m, e) == ('enter_s1', machine, None)
    a, m, e = await queue.get()
    assert (a, m, e) == ('enter_s2', machine, None)
    a, m, e = await queue.get()
    assert (a, m, e) == ('enter_s3', machine, None)
    assert machine.state == 's3'

    await asyncio.sleep(0.001)
    assert queue.empty()

    event = stc.Event('e1', 123)
    machine.register(event)
    a, m, e = await queue.get()
    assert (a, m, e) == ('exit_s3', machine, event)
    a, m, e = await queue.get()
    assert (a, m, e) == ('transit1', machine, event)
    a, m, e = await queue.get()
    assert (a, m, e) == ('enter_s4', machine, event)
    assert machine.state == 's4'

    await asyncio.sleep(0.001)
    assert queue.empty()

    event = stc.Event('e2', 123)
    machine.register(event)
    a, m, e = await queue.get()
    assert (a, m, e) == ('exit_s4', machine, event)
    a, m, e = await queue.get()
    assert (a, m, e) == ('exit_s2', machine, event)
    a, m, e = await queue.get()
    assert (a, m, e) == ('exit_s1', machine, event)
    a, m, e = await queue.get()
    assert (a, m, e) == ('transit2', machine, event)
    a, m, e = await queue.get()
    assert (a, m, e) == ('enter_s1', machine, event)
    a, m, e = await queue.get()
    assert (a, m, e) == ('enter_s2', machine, event)
    a, m, e = await queue.get()
    assert (a, m, e) == ('enter_s3', machine, event)
    assert machine.state == 's3'

    f.cancel()
    with pytest.raises(asyncio.CancelledError):
        await f
