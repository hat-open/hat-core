import asyncio
import hat.stc

door_states = hat.stc.parse_scxml('door_01.scxml')

class Door:

    def __init__(self):
        actions = {'printState': self._act_print_state}
        self._stc = hat.stc.Statechart(door_states, actions)
        self._run_task = asyncio.create_task(self._stc.run())

    def close(self):
        print('registering close event')
        self._stc.register(hat.stc.Event('close'))

    def open(self):
        print('registering open event')
        self._stc.register(hat.stc.Event('open'))

    def finish(self):
        self._run_task.cancel()

    def _act_print_state(self, inst, evt):
        print('current state:', self._stc.state)

async def main():
    door = Door()
    await asyncio.sleep(1)

    door.close()
    await asyncio.sleep(1)

    door.open()
    await asyncio.sleep(1)

    door.finish()

if __name__ == '__main__':
    asyncio.run(main())
