"""Python ctypes wrapper for duktape JavaScript interpreter

Attributes:
    default (Optional[Lib]): default duktape instanc
    default_duktape_path (pathlib.Path): default duktape library path


"""

import ctypes
import pathlib
import sys


default = None

default_duktape_path = (pathlib.Path(__file__).parent / 'duktape').with_suffix(
    '.dll' if sys.platform == 'win32' else '.so')


def init(path=None):
    """Initialize default ducktape instance

    Args:
        path (Optional[path]): dynamic library file path

    Returns:
        Lib

    """
    global default
    default = Lib(path)
    return default


class Lib:
    """Ducktape library

    Low-level interface to ducktape directly mapping ducktape functions and
    constants to python. Only parts used by :class:`Interpreter` are
    exposed. For detailed documentation see `<https://duktape.org/api.html>`_.

    Args:
        path (Optional[path]): dynamic library file path

    """

    def __init__(self, path=None):
        path = path or default_duktape_path
        lib = ctypes.cdll.LoadLibrary(str(path))
        self._init_functions(lib)
        self._init_constants(lib)

    def _init_functions(self, lib):
        duk_size_t = ctypes.c_size_t
        duk_int_t = ctypes.c_int
        duk_uint_t = ctypes.c_uint
        duk_small_int_t = ctypes.c_int
        duk_small_uint_t = ctypes.c_uint
        duk_bool_t = duk_small_uint_t
        duk_idx_t = duk_int_t
        duk_uarridx_t = duk_uint_t
        duk_ret_t = duk_small_int_t
        duk_double_t = ctypes.c_double
        duk_context_p = ctypes.c_void_p

        self.duk_c_function = ctypes.CFUNCTYPE(duk_ret_t,
                                               duk_context_p)
        self.duk_fatal_function = ctypes.CFUNCTYPE(None,
                                                   ctypes.c_void_p,
                                                   ctypes.c_char_p)

        functions = [
            (None, 'duk_call', [duk_context_p,
                                duk_idx_t]),
            (duk_context_p, 'duk_create_heap', [ctypes.c_void_p,
                                                ctypes.c_void_p,
                                                ctypes.c_void_p,
                                                ctypes.c_void_p,
                                                self.duk_fatal_function]),
            (None, 'duk_destroy_heap', [duk_context_p]),
            (None, 'duk_enum', [duk_context_p,
                                duk_idx_t,
                                duk_uint_t]),
            (duk_int_t, 'duk_eval_raw', [duk_context_p,
                                         ctypes.c_char_p,
                                         duk_size_t,
                                         duk_uint_t]),
            (duk_bool_t, 'duk_get_boolean', [duk_context_p,
                                             duk_idx_t]),
            (duk_bool_t, 'duk_get_global_string', [duk_context_p,
                                                   ctypes.c_char_p]),
            (ctypes.c_void_p, 'duk_get_heapptr', [duk_context_p,
                                                  duk_idx_t]),
            (duk_double_t, 'duk_get_number', [duk_context_p,
                                              duk_idx_t]),
            (ctypes.c_char_p, 'duk_get_string', [duk_context_p,
                                                 duk_idx_t]),
            (duk_idx_t, 'duk_get_top', [duk_context_p]),
            (duk_uint_t, 'duk_get_type_mask', [duk_context_p,
                                               duk_idx_t]),
            (duk_bool_t, 'duk_is_array', [duk_context_p,
                                          duk_idx_t]),
            (duk_bool_t, 'duk_is_boolean', [duk_context_p,
                                            duk_idx_t]),
            (duk_bool_t, 'duk_is_function', [duk_context_p,
                                             duk_idx_t]),
            (duk_bool_t, 'duk_is_number', [duk_context_p,
                                           duk_idx_t]),
            (duk_bool_t, 'duk_is_object', [duk_context_p,
                                           duk_idx_t]),
            (duk_bool_t, 'duk_is_string', [duk_context_p,
                                           duk_idx_t]),
            (duk_bool_t, 'duk_next', [duk_context_p,
                                      duk_idx_t,
                                      duk_bool_t]),
            (duk_idx_t, 'duk_push_array', [duk_context_p]),
            (None, 'duk_push_boolean', [duk_context_p,
                                        duk_bool_t]),
            (duk_idx_t, 'duk_push_c_function', [duk_context_p,
                                                self.duk_c_function,
                                                duk_idx_t]),
            (duk_idx_t, 'duk_push_heapptr', [duk_context_p,
                                             ctypes.c_void_p]),
            (None, 'duk_push_heap_stash', [duk_context_p]),
            (None, 'duk_push_null', [duk_context_p]),
            (None, 'duk_push_number', [duk_context_p,
                                       duk_double_t]),
            (duk_idx_t, 'duk_push_object', [duk_context_p]),
            (ctypes.c_char_p, 'duk_push_string', [duk_context_p,
                                                  ctypes.c_char_p]),
            (duk_bool_t, 'duk_put_global_string', [duk_context_p,
                                                   ctypes.c_char_p]),
            (duk_bool_t, 'duk_put_prop_index', [duk_context_p,
                                                duk_idx_t,
                                                duk_uarridx_t]),
            (duk_bool_t, 'duk_put_prop_string', [duk_context_p,
                                                 duk_idx_t,
                                                 ctypes.c_char_p]),
            (None, 'duk_set_top', [duk_context_p,
                                   duk_idx_t])
        ]

        for restype, name, argtypes in functions:
            function = getattr(lib, name)
            function.argtypes = argtypes
            function.restype = restype
            setattr(self, name, function)

    def _init_constants(self, lib):
        DUK_ERR_ERROR = 1
        DUK_COMPILE_EVAL = (1 << 3)
        DUK_COMPILE_NOSOURCE = (1 << 9)
        DUK_COMPILE_STRLEN = (1 << 10)
        DUK_COMPILE_NOFILENAME = (1 << 11)
        DUK_TYPE_MASK_UNDEFINED = (1 << 1)
        DUK_TYPE_MASK_NULL = (1 << 2)

        self.DUK_ENUM_OWN_PROPERTIES_ONLY = (1 << 4)
        self.DUK_ENUM_ARRAY_INDICES_ONLY = (1 << 5)
        self.DUK_VARARGS = -1
        self.DUK_RET_ERROR = - DUK_ERR_ERROR

        self.duk_eval_string = lambda ctx, src: lib.duk_eval_raw(
            ctx, src, 0,
            0 | DUK_COMPILE_EVAL | DUK_COMPILE_NOSOURCE |
            DUK_COMPILE_STRLEN | DUK_COMPILE_NOFILENAME)

        self.duk_is_null_or_undefined = lambda ctx, idx: bool(
            lib.duk_get_type_mask(ctx, idx) &
            (DUK_TYPE_MASK_NULL | DUK_TYPE_MASK_UNDEFINED))


class Interpreter:
    """JavaScript interpreter

    High-level python wrapper to duktape JavaScript interpreter.

    Current implementation caches all function objects for preventing
    garbage collection.

    Args:
        lib (Optional[Lib]): duktape library

    """

    def __init__(self, lib=None):
        self._lib = lib or default or init()

        @self._lib.duk_fatal_function
        def fatal_handler(udata, msg):
            try:
                print(f"duktape fatal error: {msg.decode('utf-8')}")
            finally:
                sys.exit(1)

        self._ctx = self._lib.duk_create_heap(None, None, None, None,
                                              fatal_handler)
        self._fns = [fatal_handler]

    def __del__(self):
        self._lib.duk_destroy_heap(self._ctx)
        self._fns = []

    def eval(self, code):
        """Evaluate JS code

        Args:
            code (str): JS code

        Returns:
            Any

        """
        top = self._lib.duk_get_top(self._ctx)
        try:
            self._lib.duk_eval_string(self._ctx, code.encode('utf-8'))
            return self._peek(-1)
        finally:
            self._lib.duk_set_top(self._ctx, top)

    def get(self, name):
        """Get global value

        Args:
            name (str): global name

        Returns:
            Any

        """
        top = self._lib.duk_get_top(self._ctx)
        try:
            key = name.encode('utf-8')
            self._lib.duk_get_global_string(self._ctx, key)
            return self._peek(-1)
        finally:
            self._lib.duk_set_top(self._ctx, top)

    def set(self, name, value):
        """Set global value

        Args:
            name (str): global name
            value (Any): value

        """
        top = self._lib.duk_get_top(self._ctx)
        try:
            self._push(value)
            key = name.encode('utf-8')
            self._lib.duk_put_global_string(self._ctx, key)
        finally:
            self._lib.duk_set_top(self._ctx, top)

    def _peek(self, idx):
        if self._lib.duk_is_null_or_undefined(self._ctx, idx):
            return
        if self._lib.duk_is_boolean(self._ctx, idx):
            return self._peek_boolean(idx)
        if self._lib.duk_is_number(self._ctx, idx):
            return self._peek_number(idx)
        if self._lib.duk_is_string(self._ctx, idx):
            return self._peek_string(idx)
        if self._lib.duk_is_array(self._ctx, idx):
            return self._peek_array(idx)
        if self._lib.duk_is_function(self._ctx, idx):
            return self._peek_function(idx)
        if self._lib.duk_is_object(self._ctx, idx):
            return self._peek_object(idx)
        raise ValueError()

    def _peek_boolean(self, idx):
        return bool(self._lib.duk_get_boolean(self._ctx, idx))

    def _peek_number(self, idx):
        return self._lib.duk_get_number(self._ctx, idx)

    def _peek_string(self, idx):
        return self._lib.duk_get_string(self._ctx, idx).decode('utf-8')

    def _peek_array(self, idx):
        result = []
        top = self._lib.duk_get_top(self._ctx)
        self._lib.duk_enum(self._ctx, idx,
                           self._lib.DUK_ENUM_ARRAY_INDICES_ONLY)
        try:
            while self._lib.duk_next(self._ctx, top, 1):
                result.append(self._peek(-1))
        finally:
            self._lib.duk_set_top(self._ctx, top)
        return result

    def _peek_object(self, idx):
        result = {}
        top = self._lib.duk_get_top(self._ctx)
        self._lib.duk_enum(self._ctx, idx,
                           self._lib.DUK_ENUM_OWN_PROPERTIES_ONLY)
        try:
            while self._lib.duk_next(self._ctx, top, 1):
                key = self._peek(-2)
                value = self._peek(-1)
                result[key] = value
        finally:
            self._lib.duk_set_top(self._ctx, top)
        return result

    def _peek_function(self, idx):
        fn_ptr = self._lib.duk_get_heapptr(self._ctx, idx)
        self._stash(fn_ptr)

        def wrapper(*args):
            top = self._lib.duk_push_heapptr(self._ctx, fn_ptr)
            try:
                for arg in args:
                    self._push(arg)
                self._lib.duk_call(self._ctx, len(args))
                return self._peek(-1)
            finally:
                self._lib.duk_set_top(self._ctx, top)

        return wrapper

    def _push(self, value):
        if value is None:
            self._push_null()
        elif isinstance(value, bool):
            self._push_boolean(value)
        elif isinstance(value, int) or isinstance(value, float):
            self._push_number(value)
        elif isinstance(value, str):
            self._push_string(value)
        elif isinstance(value, list) or isinstance(value, tuple):
            self._push_array(value)
        elif isinstance(value, dict):
            self._push_object(value)
        elif callable(value):
            self._push_function(value)
        else:
            raise ValueError()

    def _push_null(self):
        self._lib.duk_push_null(self._ctx)

    def _push_boolean(self, value):
        self._lib.duk_push_boolean(self._ctx, value)

    def _push_number(self, value):
        self._lib.duk_push_number(self._ctx, value)

    def _push_string(self, value):
        self._lib.duk_push_string(self._ctx, value.encode('utf-8'))

    def _push_array(self, value):
        arr_idx = self._lib.duk_push_array(self._ctx)
        try:
            for index, element in enumerate(value):
                self._push(element)
                if self._lib.duk_put_prop_index(self._ctx, arr_idx,
                                                index) != 1:
                    raise Exception('could not add element to array')
        except Exception:
            self._lib.duk_set_top(self._ctx, arr_idx)
            raise

    def _push_object(self, value):
        obj_idx = self._lib.duk_push_object(self._ctx)
        try:
            for k, v in value.items():
                self._push(v)
                if self._lib.duk_put_prop_string(self._ctx, obj_idx,
                                                 k.encode('utf-8')) != 1:
                    raise Exception('could not add property to object')
        except Exception:
            self._lib.duk_set_top(self._ctx, obj_idx)
            raise

    def _push_function(self, value):

        @self._lib.duk_c_function
        def wrapper(ctx):
            args = []
            args_count = self._lib.duk_get_top(self._ctx)
            try:
                for i in range(args_count):
                    args.append(self._peek(i))
                result = value(*args)
                self._push(result)
            except Exception:
                return self._lib.DUK_RET_ERROR
            return 1

        self._lib.duk_push_c_function(self._ctx, wrapper,
                                      self._lib.DUK_VARARGS)
        self._fns.append(wrapper)

    def _stash(self, ptr):
        top = self._lib.duk_get_top(self._ctx)
        try:
            ptr_id = int(ptr)
            self._lib.duk_push_heap_stash(self._ctx)
            self._lib.duk_push_heapptr(self._ctx, ptr)
            if self._lib.duk_put_prop_index(self._ctx, -2, ptr_id) != 1:
                raise Exception("couldn't stash pointer")
        finally:
            self._lib.duk_set_top(self._ctx, top)
