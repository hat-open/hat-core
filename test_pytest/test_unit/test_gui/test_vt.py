import io

import pytest

import hat.gui.vt


@pytest.mark.parametrize('xml, vt', [
    ('<div></div>',
     ['div']),

    ('<div><tag/>Text</div>',
     ['div', ['tag'], 'Text']),

    ('<div id="xyz"></div>',
     ['div#xyz']),

    ('<div class="abc"></div>',
     ['div.abc']),

    ('<div class="abc def"></div>',
     ['div.abc.def']),

    ('<div id="xyz" class="abc"></div>',
     ['div#xyz.abc']),

    ('<div id="xyz" class="abc" style="width: 10px;"></div>',
     ['div#xyz.abc', {'attrs': {'style': 'width: 10px;'}}]),
])
def test_parse(xml, vt):
    stream = io.StringIO(xml)
    result = hat.gui.vt.parse(stream)
    assert vt == result
