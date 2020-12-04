"""Translator definition"""

import typing

from hat import json
from hat import util


Translate = typing.Callable[[json.Data], json.Data]
"""Translate function type"""


Translator = util.namedtuple(
    ['Translator', """Translator definition

    Translators are dynamicly loaded from python modules that contain:

        * translators (List[Translator]): translators

    """],
    ['input_type', 'str: input configuration type'],
    ['input_schema', 'Optional[str]: input JSON schema identifier'],
    ['output_type', 'str: output configuration type'],
    ['output_schema', 'Optional[str]: output JSON schema identifier'],
    ['translate', 'Translate: translate function'])
