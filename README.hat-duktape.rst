Hat Core - Python Duktape wrapper
=================================

This library is part of Hat Open project - open-source framework of tools and
libraries for developing applications used for remote monitoring, control and
management of intelligent electronic devices such as IoT devices, PLCs,
industrial automation or home automation systems.

Development of Hat Open and associated repositories is sponsored by
Končar - Power Plant and Electric Traction Engineering Inc.
(Končar KET - `<https://www.koncar-ket.hr>`_).

For more information see:

    * `hat-duktape` documentation - `<https://core.hat-open.com/docs/libraries/duktape.html>`_
    * Hat Core homepage - `<https://core.hat-open.com>`_
    * Hat Core git repository - `<https://github.com/hat-open/hat-core.git>`_

.. warning::

    This project is currently in state of active development. Features,
    functionality and API are unstable.


About
-----

Python ctypes wrapper for JavaScript Duktape engine with minimal API::

    Data = typing.Union[None, bool, int, float, str,
                        typing.List['Data'], typing.Dict[str, 'Data'],
                        typing.Callable]

    class Interpreter:

        def __init__(self): ...

        def eval(self,
                 code: str,
                 with_result: bool = True
                 ) -> Data:
            """Evaluate JS code and optionally return last expression"""

        def get(self, name: str) -> Data:
            """Get global value"""

        def set(self, name: str, value: Data):
            """Set global value"""
