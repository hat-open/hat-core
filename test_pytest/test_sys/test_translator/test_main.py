import subprocess
from pathlib import Path

import pytest

from hat import util
from hat.util import json
from hat.translator import common


translators = [
    common.Translator(input_type='t1_without_schema',
                      input_schema=None,
                      output_type='t2_without_schema',
                      output_schema=None,
                      translate=lambda x: x),
    common.Translator(input_type='t1_with_schema',
                      input_schema='test://test_main.yaml#/definitions/t1',
                      output_type='t2_with_schema',
                      output_schema='test://test_main.yaml#/definitions/t2',
                      translate=lambda x: str(x)),
    common.Translator(input_type='t1_with_schema',
                      input_schema='test://test_main.yaml#/definitions/t1',
                      output_type='invalid_t2_with_schema',
                      output_schema='test://test_main.yaml#/definitions/t2',
                      translate=lambda x: x),
    common.Translator(input_type='invalid_t1_with_schema',
                      input_schema='test://test_main.yaml#/definitions/t1',
                      output_type='t2_with_schema',
                      output_schema='test://test_main.yaml#/definitions/t2',
                      translate=lambda x: x)
]


@pytest.fixture(params=[json.Format.JSON, json.Format.YAML])
def run_translator(request):
    format = request.param

    def run_translator(action, args, data=None, decode=True):
        data_str = (json.encode(data, format=format) if data is not None
                    else None)
        p = subprocess.run(
            ['python', '-m', 'hat.translator',
             '--json-schemas-path',
             str(json.default_schemas_json_path),
             action,
             '--format', format.name.lower(),
             '--module', 'test_sys.test_translator.test_main',
             '--additional-json-schemas-path',
             str(Path(__file__).with_suffix('.yaml'))] + args,
            input=data_str, stdout=subprocess.PIPE, check=True,
            stderr=subprocess.DEVNULL, universal_newlines=True)
        return json.decode(p.stdout, format=format) if decode else p.stdout

    return run_translator


def test_list(run_translator):
    result = run_translator('list', [])
    for i in translators:
        assert util.first(
            result, lambda x: (x['input_type'] == i.input_type) and
                              (x['input_schema'] == i.input_schema) and
                              (x['output_type'] == i.output_type) and
                              (x['output_schema'] == i.output_schema))


def test_valid(run_translator):
    data = 'abc'
    result = run_translator('translate',
                            ['--input-type', 't1_without_schema',
                             '--output-type', 't2_without_schema'], data)
    assert data == result

    data = 123
    result = run_translator('translate',
                            ['--input-type', 't1_with_schema',
                             '--output-type', 't2_with_schema'], data)
    assert str(data) == result


def test_invalid(run_translator):
    data = 123
    with pytest.raises(Exception):
        run_translator('translate',
                       ['--input-type', 't1_with_schema',
                        '--output-type', 'invalid_t2_with_schema'], data)

    data = 'abc'
    with pytest.raises(Exception):
        run_translator('translate',
                       ['--input-type', 'invalid_t1_with_schema',
                        '--output-type', 't2_with_schema'], data)

    data = 'abc'
    with pytest.raises(Exception):
        run_translator('translate',
                       ['--input-type', 'abc',
                        '--output-type', 'xyz'], data)
