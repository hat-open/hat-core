import asyncio
import hat.stc

async def main():

    def act_print_state(door, evt):
        print('current state:', door.state)

    states = hat.stc.parse_scxml("door_01.scxml")
    actions = {'printState': act_print_state}
    door = hat.stc.Statechart(states, actions)

    # TODO: run statechart

if __name__ == '__main__':
    asyncio.run(main())
