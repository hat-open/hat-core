import asyncio
import base64
import io
import json
import jsonschema
import pytest
import xml.sax
import yaml

from hat import aio
import hat.gui.view
import hat.gui.vt
import hat.json

from test_unit.test_gui import common


@pytest.mark.parametrize('views', [
    {
        'view1': [
            common.FileDescriptor(
                relative_path='src_js/test.js',
                serialization_method=common.SerializationMethod.TEXT,
                content="console.log('Hello world!')"),
            common.FileDescriptor(
                relative_path='src_js/test2.js',
                serialization_method=common.SerializationMethod.TEXT,
                content="console.log('Hello world! (2)')")],
        'view2': [
            common.FileDescriptor(
                relative_path='test.css',
                serialization_method=common.SerializationMethod.TEXT,
                content='body { background-color: pink; }'),
            common.FileDescriptor(
                relative_path='test.txt',
                serialization_method=common.SerializationMethod.TEXT,
                content='Lorem ipsum...')]},
    {
        'view1': [
            common.FileDescriptor(
                relative_path='src_json/test.json',
                serialization_method=common.SerializationMethod.JSON,
                content={'a': 'b', 'c': 'd', 'e': 'f'}),
            common.FileDescriptor(
                relative_path='src_yaml/test.yaml',
                serialization_method=common.SerializationMethod.YAML,
                content={'g': 'h', 'i': 'j', 'k': 'l'})],
        'view2': [
            common.FileDescriptor(
                relative_path='src_yaml/test.yml',
                serialization_method=common.SerializationMethod.YAML,
                content={'m': 'n', 'o': 'p', 'q': 'r'})]}
])
@pytest.mark.asyncio
async def test_unchanging_content(view_factory, view_manager_factory, views):
    conf = []
    for view_name, file_descriptors in views.items():
        conf.append(view_factory(view_name, file_descriptors))

    view_manager = await view_manager_factory(conf)
    for view_name, file_descriptors in views.items():
        view = await view_manager.get(view_name)
        assert view.name == view_name
        assert view.conf is None
        for fd in file_descriptors:
            assert fd.relative_path in view.data
            assert fd.content == view.data[fd.relative_path]


@pytest.mark.asyncio
async def test_binary_content(view_factory, view_manager_factory):
    view_name = 'binaries_view'
    file_descriptors = [
        common.FileDescriptor(
            relative_path='test.bin',
            serialization_method=common.SerializationMethod.BINARY,
            content='Hello world'.encode('utf-8')),
        common.FileDescriptor(
            relative_path='test2.bin',
            serialization_method=common.SerializationMethod.BINARY,
            content='Hello2'.encode('utf-8'))]
    conf = [view_factory(view_name, file_descriptors)]

    view_manager = await view_manager_factory(conf)
    view = await view_manager.get(view_name)
    assert view.name == view_name
    assert view.conf is None
    for fd in file_descriptors:
        assert fd.relative_path in view.data
        assert fd.content == base64.b64decode(
            view.data[fd.relative_path].encode('utf-8'))


@pytest.mark.asyncio
async def test_xml_content(view_factory, view_manager_factory):
    view_name = 'binaries_view'
    file_descriptors = [
        common.FileDescriptor(
            relative_path='test.xml',
            serialization_method=common.SerializationMethod.TEXT,
            content='<div id="123"><div/></div>'),
        common.FileDescriptor(
            relative_path='test2.svg',
            serialization_method=common.SerializationMethod.TEXT,
            content='<svg></svg>')]
    conf = [view_factory(view_name, file_descriptors)]
    view_manager = await view_manager_factory(conf)

    view = await view_manager.get(view_name)
    assert view.name == view_name
    assert view.conf is None
    for fd in file_descriptors:
        assert fd.relative_path in view.data
        stream = io.StringIO(fd.content)
        assert hat.gui.vt.parse(stream) == view.data[fd.relative_path]


@pytest.mark.parametrize('file_descriptor, exception_cls', [
    (common.FileDescriptor(
        relative_path='test.xml',
        serialization_method=common.SerializationMethod.TEXT,
        content='invalid xml</div>'), xml.sax.SAXParseException),
    (common.FileDescriptor(
        relative_path='test.json',
        serialization_method=common.SerializationMethod.TEXT,
        content='{"key": "value", this should not be here}'),
     json.decoder.JSONDecodeError),
    (common.FileDescriptor(
        relative_path='test.yaml',
        serialization_method=common.SerializationMethod.TEXT,
        content='{"key": "value"123, this should not be here}'),
     yaml.parser.ParserError)])
@pytest.mark.asyncio
async def test_invalid_file(view_factory, view_manager_factory,
                            file_descriptor, exception_cls):
    view_name = 'invalid_view'
    conf = [view_factory(view_name, [file_descriptor])]
    view_manager = await view_manager_factory(conf)

    with pytest.raises(exception_cls):
        await view_manager.get(view_name)


@pytest.mark.asyncio
async def test_conf_returned(view_factory, view_manager_factory):
    file_descriptors = []
    conf = {'abc': 'def'}
    view_name = 'test_conf_returned'

    manager_conf = [view_factory(view_name, file_descriptors, conf)]
    view_manager = await view_manager_factory(manager_conf)

    view = await view_manager.get(view_name)
    assert view.name == view_name
    assert view.conf == conf


@pytest.mark.asyncio
async def test_conf_validated(view_factory, view_manager_factory):
    conf_schema = """
        type: object
        id: hat://test_schema
        required:
            - required_property
        properties:
            required_property:
                type: string
        """
    file_descriptors = [
        common.FileDescriptor(
            relative_path='schema.yaml',
            serialization_method=common.SerializationMethod.TEXT,
            content=conf_schema)]
    conf = {'abc': 'def'}
    view_name = 'test_conf_validated'
    manager_conf = [view_factory(view_name, file_descriptors, conf)]
    view_manager = await view_manager_factory(manager_conf)

    with pytest.raises(jsonschema.ValidationError):
        await view_manager.get(view_name)


@pytest.mark.asyncio
async def test_view_manager_closed(view_factory, view_manager_factory):
    view_manager = await view_manager_factory([view_factory('view', [])])
    view = await view_manager.get('view')
    assert view.data == {}

    await view_manager.async_close()

    with pytest.raises(Exception, match='view manager is closed'):
        view = await view_manager.get('view')


@pytest.mark.asyncio
async def test_view_manager_closing(view_factory, view_manager_factory):
    view_manager = await view_manager_factory([view_factory('view', [])])
    view = await view_manager.get('view')
    assert view.data == {}

    async with aio.Group() as group:
        group.spawn(view_manager.async_close)

        with pytest.raises(asyncio.CancelledError):
            await view_manager.get('view')
