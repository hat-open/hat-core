import asyncio
import hat.stc

door_states = hat.stc.parse_scxml('door_04.scxml')

class Door:

    def __init__(self):
        actions = {'logEnter': self._act_log_enter,
                   'logExit': self._act_log_exit,
                   'logTransition': self._act_log_transition,
                   'logInvalid': self._act_log_invalid,
                   'startTimer': self._act_start_timer,
                   'stopTimer': self._act_stop_timer}
        self._stc = hat.stc.Statechart(door_states, actions)
        self._timer = None
        self._run_task = asyncio.create_task(self._stc.run())

    def finish(self):
        self._run_task.cancel()

    def close(self, force):
        print('registering close event')
        self._stc.register(hat.stc.Event('close', force))

    def open(self, force):
        print('registering open event')
        self._stc.register(hat.stc.Event('open', force))

    def _act_log_enter(self, evt):
        print(f'entering state {self._stc.state}')

    def _act_log_exit(self, evt):
        print(f'exiting state {self._stc.state}')

    def _act_log_transition(self, evt):
        print(f'transitioning because of event {evt}')

    def _act_log_invalid(self, evt):
        print(f'invalid operation {evt.name} in state {self._stc.state}')

    def _act_start_timer(self, evt):
        force = evt.payload
        delay = force_to_delay(force)
        print(f'waiting for {delay} seconds')
        loop = asyncio.get_event_loop()
        self._timer = loop.call_later(delay, self._stc.register,
                                      hat.stc.Event('timeout'))

    def _act_stop_timer(self, evt):
        self._timer.cancel()

def force_to_delay(force):
    if force <= 0:
        return 0.1
    if force >= 100:
        return 0
    return (100 - force) * 0.001

async def main():
    door = Door()
    await asyncio.sleep(1)

    door.open(10)
    await asyncio.sleep(1)

    door.close(20)
    await asyncio.sleep(1)

    door.close(30)
    await asyncio.sleep(1)

    door.finish()

if __name__ == '__main__':
    asyncio.run(main())
