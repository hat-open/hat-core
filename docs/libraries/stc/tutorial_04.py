import asyncio
import hat.stc

door_states = hat.stc.parse_scxml('door_01.scxml')

class Door:

    def __init__(self):
        actions = {'printState': self._act_print_state}
        self._stc = hat.stc.Statechart(door_states, actions)
        self._run_task = asyncio.create_task(self._stc.run())

    def finish(self):
        self._run_task.cancel()

    def close(self, force):
        print('registering close event')
        self._stc.register(hat.stc.Event('close', force))

    def open(self, force):
        print('registering open event')
        self._stc.register(hat.stc.Event('open', force))

    def _act_print_state(self, inst, evt):
        force = evt.payload if evt else None
        print(f'force {force} caused transition to {self._stc.state}')

async def main():
    print("1. example:")
    door = Door()
    await asyncio.sleep(1)

    door.close(10)
    await asyncio.sleep(1)

    door.open(20)
    await asyncio.sleep(1)

    door.finish()
    print('---')

    print("2. example:")
    door = Door()
    door.close(20)
    door.open(50)

    await asyncio.sleep(1)
    door.finish()
    print('---')

    print("3. example:")
    door = Door()
    door.open(10)
    door.close(20)
    door.close(30)
    door.open(40)

    await asyncio.sleep(1)
    door.finish()
    print('---')

if __name__ == '__main__':
    asyncio.run(main())
