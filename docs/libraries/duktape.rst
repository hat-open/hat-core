`hat.duktape` - Python Duktape wrapper
======================================

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


API
---

API reference is available as part of generated documentation:

    * `Python hat.duktape module <../pyhat/hat/duktape/index.html>`_
