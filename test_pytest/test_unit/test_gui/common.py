import enum
import json
import yaml

from hat import util


class SerializationMethod(enum.Enum):
    TEXT = 1
    JSON = 2
    YAML = 3
    BINARY = 4


FileDescriptor = util.namedtuple(
    'FileDescriptor',
    ['relative_path', 'str'],
    ['serialization_method', 'SerializationMethod'],
    ['content', 'Any'])


def write_file(path, content, serialization_method):
    path.parent.mkdir(exist_ok=True)
    if serialization_method == SerializationMethod.TEXT:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    elif serialization_method == SerializationMethod.JSON:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(content, f)
    elif serialization_method == SerializationMethod.YAML:
        with open(path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(content, f)
    elif serialization_method == SerializationMethod.BINARY:
        with open(path, 'wb') as f:
            f.write(content)


def create_view_files(view_path, file_descriptors, conf_path=None, conf=None):
    for file_descriptor in file_descriptors:
        write_file(view_path / file_descriptor.relative_path,
                   file_descriptor.content,
                   file_descriptor.serialization_method)
    if conf_path is not None:
        write_file(conf_path, conf, SerializationMethod.YAML)
