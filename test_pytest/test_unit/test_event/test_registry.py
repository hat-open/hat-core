import pytest

from hat.event.server.registry import (EventTypeRegistryStorage,
                                       create_event_type_registry)


pytestmark = pytest.mark.asyncio


class MockEventTypeRegistryStorage(EventTypeRegistryStorage):

    def __init__(self, mappings):
        self._mappings = mappings

    @property
    def mappings(self):
        return self._mappings

    async def get_event_type_mappings(self):
        return self._mappings

    async def add_event_type_mappings(self, mappings):
        self._mappings.update(mappings)


async def test_event_type_registry_get_event_type():
    storage = MockEventTypeRegistryStorage({})
    registry = await create_event_type_registry(storage)
    with pytest.raises(Exception):
        registry.get_event_type(0)
    with pytest.raises(Exception):
        registry.get_event_type(1)

    storage = MockEventTypeRegistryStorage({1: ('a', 'b', 'c'),
                                            5: ('x', 'y', 'z')})
    registry = await create_event_type_registry(storage)
    assert len(storage.mappings) == 6
    assert registry.get_event_type(1) == ('a', 'b', 'c')
    assert registry.get_event_type(5) == ('x', 'y', 'z')
    with pytest.raises(Exception):
        registry.get_event_type(3)


async def test_event_type_registry_get_identifiers():
    storage = MockEventTypeRegistryStorage({})
    registry = await create_event_type_registry(storage)

    assert len(storage.mappings) == 0

    ids = await registry.get_identifiers([('a',), ('b', 'c')])
    assert len(storage.mappings) == 3
    assert len(ids) == 2
    for i in ids:
        assert isinstance(i, int)

    ids = await registry.get_identifiers([('b',)])
    assert len(storage.mappings) == 3
    assert len(ids) == 1
    assert isinstance(ids[0], int)

    event_types = [('a', 'b', 'c'),
                   ('x', 'y', 'z')]
    ids = await registry.get_identifiers(event_types)
    assert len(event_types) == len(ids)
    for event_type, event_type_id in zip(event_types, ids):
        assert registry.get_event_type(event_type_id) == event_type


async def test_event_type_registry_query_identifiers():
    storage = MockEventTypeRegistryStorage({1: ('a',),
                                            2: ('a', 'b'),
                                            3: ('a', 'c'),
                                            4: ('a', 'b', 'd')})
    registry = await create_event_type_registry(storage)

    ids = registry.query_identifiers([()])
    assert len(ids) == 0

    ids = registry.query_identifiers([('*',)])
    assert ids == {1, 2, 3, 4}

    ids = registry.query_identifiers([('a', '*')])
    assert ids == {1, 2, 3, 4}

    ids = registry.query_identifiers([('a', 'b', '*')])
    assert ids == {2, 4}

    ids = registry.query_identifiers([('a', '?')])
    assert ids == {2, 3}

    ids = registry.query_identifiers([('a', '?', '?')])
    assert ids == {4}

    ids = registry.query_identifiers([('a', '?', 'd')])
    assert ids == {4}

    ids = registry.query_identifiers([('a', '?', 'a')])
    assert len(ids) == 0

    ids = registry.query_identifiers([('a', '?', '*')])
    assert ids == {2, 3, 4}
