from .archlinux import *  # NOQA
from .key import *  # NOQA
from .win10 import *  # NOQA
from . import archlinux
from . import key
from . import win10


__all__ = (archlinux.__all__ +
           key.__all__ +
           win10.__all__)
