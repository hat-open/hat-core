"""Mebo robot communication driver

Actions:

| name          | params | returns | description |
+===============+========+
| get_version   |        | ?:<version> | |
+---------------+
| get_boundary_position | | ?:s_up=<s_up>&
                              s_down=<s_down>&
                              c_open=<c_open>&
                              c_close=<c_close>&
                              w_left=<w_left>&
                              w_right=<w_right>&
                              h_up=<h_up>&
                              h_down=<h_down>
+---------------+
| move_forward        | speed (int - 0...255) |
| move_forward_right  | dur (int - ms)
| move_right          |
| move_backward_right |
| move_backward       |
| move_backward_left  |
| move_left           |
| move_forward_left   |
+---------------+
| inch_right | direction (str - 'r', 'l') |
| inch_left  |
+------------+
| fb_stop    |  |
+------------+
| c_open        | dur (int - ms)
| c_close
+-------------
| w_right |
| inch_w_right
| w_left
| inch_w_left
| w_stop
| h_up
| h_down
| h_stop
+-------------
| s_up      | dur (int - ms)
| s_down
+-------------
| s_stop

"""

import aiohttp


class Mebo:

    def __init__(self, host, port=80):
        self._host = host
        self._port = port
        self._session = aiohttp.ClientSession()

    async def request(self, action, **params):
        addr = f'http://{self._host}:{self._port}/ajax/command.json'
        # params = dict(params, req=action)
        params = {
            'command1': 'mebolink_message_send(VER)'
        }
        async with self._session.get(addr, params=params) as resp:
            return await resp.text()
