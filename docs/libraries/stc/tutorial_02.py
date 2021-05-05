import asyncio
import hat.stc

async def main():

    def act_print_state(door, evt):
        print('current state:', door.state)

    states = hat.stc.parse_scxml("door_01.scxml")
    actions = {'printState': act_print_state}
    door = hat.stc.Statechart(states, actions)

    run_task = asyncio.create_task(door.run())
    await asyncio.sleep(1)

    print('registering close event')
    door.register(hat.stc.Event('close'))
    await asyncio.sleep(1)

    print('registering open event')
    door.register(hat.stc.Event('open'))
    await asyncio.sleep(1)

    run_task.cancel()

if __name__ == '__main__':
    asyncio.run(main())
