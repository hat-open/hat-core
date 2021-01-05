import asyncio
import contextlib
from datetime import datetime, timezone
import pytest
import math

from hat import aio
from hat.drivers import mms


@pytest.fixture
def server_factory(unused_tcp_port_factory):

    @contextlib.asynccontextmanager
    async def factory(connection_cb, request_cb):
        connections = []

        async def on_connection(conn):
            connections.append(conn)
            await connection_cb(conn)

        server = await mms.listen(
            on_connection, request_cb,
            addr=mms.Address('0.0.0.0', unused_tcp_port_factory()))
        yield server
        async_group = aio.Group()
        async_group.spawn(server.async_close)
        for conn in connections:
            async_group.spawn(conn.async_close)
        await async_group.async_close(cancel=False)

    return factory


@pytest.mark.asyncio
async def test_listen(server_factory):

    async def connection_cb(connection):
        pass

    async def request_cb(connection, request):
        return mms.Response.StatusResponse(logical=1, physical=1)

    async with server_factory(connection_cb, request_cb) as server:
        assert len(server.addresses) == 1


@pytest.mark.asyncio
@pytest.mark.timeout(2)
@pytest.mark.parametrize("connection_count", [1, 2, 10])
async def test_can_connect(connection_count, server_factory):
    server_connections = []
    client_connections = []

    async def connection_cb(connection):
        server_connections.append(connection)

    async def request_cb(connection, request):
        return mms.Response.StatusResponse(logical=1, physical=1)

    async with server_factory(connection_cb, request_cb) as server:
        address = server.addresses[0]
        for _ in range(connection_count):
            conn = await mms.connect(request_cb, address)
            client_connections.append(conn)

        assert len(server_connections) == connection_count

    async_group = aio.Group()
    for conn in client_connections:
        async_group.spawn(conn.async_close)
    await async_group.async_close(cancel=False)


@pytest.mark.asyncio
@pytest.mark.timeout(2)
@pytest.mark.parametrize("req,resp", [(
        mms.StatusRequest(),
        mms.StatusResponse(logical=1, physical=1)
    ), (
        mms.GetNameListRequest(object_class=mms.ObjectClass.NAMED_VARIABLE,
                               object_scope=mms.VmdSpecificObjectScope(),
                               continue_after='123'),
        mms.GetNameListResponse(identifiers=['a', 'b', 'c'],
                                more_follows=False)
    ), (
        mms.GetNameListRequest(object_class=mms.ObjectClass.NAMED_VARIABLE,
                               object_scope=mms.AaSpecificObjectScope(),
                               continue_after='123'),
        mms.GetNameListResponse(identifiers=['a', 'b', 'c'],
                                more_follows=False)
    ), (
        mms.GetNameListRequest(
            object_class=mms.ObjectClass.NAMED_VARIABLE,
            object_scope=mms.DomainSpecificObjectScope(identifier='1234'),
            continue_after='123'),
        mms.GetNameListResponse(identifiers=['a', 'b', 'c'],
                                more_follows=False)
    ), (
        mms.IdentifyRequest(),
        mms.IdentifyResponse(vendor='a', model='b', revision='c',
                             syntaxes=None)
    ), (
        mms.IdentifyRequest(),
        mms.IdentifyResponse(vendor='a', model='b', revision='c',
                             syntaxes=[[2, 1, 3], [1, 2, 5]])
    ), (
        mms.GetVariableAccessAttributesRequest(value='x'),
        mms.GetVariableAccessAttributesResponse(
            mms_deletable=True, type_description=mms.BooleanTypeDescription())
    ), (
        mms.GetNamedVariableListAttributesRequest(
            value=mms.VmdSpecificObjectName(identifier='x')),
        mms.GetNamedVariableListAttributesResponse(
            mms_deletable=True,
            specification=[
                mms.NameVariableSpecification(
                    name=mms.DomainSpecificObjectName(domain_id='abc',
                                                      item_id='xyuz'))])
    ), (
        mms.GetVariableAccessAttributesRequest(
            value=mms.VmdSpecificObjectName(identifier='x')),
        mms.GetVariableAccessAttributesResponse(
            mms_deletable=True, type_description=mms.BooleanTypeDescription())
    ), (
        mms.ReadRequest(value=mms.VmdSpecificObjectName(identifier='x')),
        mms.ReadResponse(results=[mms.BooleanData(value=True)])
    ), (
        mms.ReadRequest(value=mms.VmdSpecificObjectName(identifier='x')),
        mms.ReadResponse(results=[mms.DataAccessError.INVALID_ADDRESS])
    ), (
        mms.WriteRequest(
            specification=mms.VmdSpecificObjectName(identifier='x'),
            data=[mms.BooleanData(value=True)]),
        mms.WriteResponse(results=[mms.DataAccessError.INVALID_ADDRESS])
    ), (
        mms.WriteRequest(
            specification=[mms.NameVariableSpecification(
                name=mms.DomainSpecificObjectName(
                    domain_id='dev', item_id='abc'))],
            data=[mms.BooleanData(value=True)]),
        mms.WriteResponse(results=[None])
    ), (
        mms.DefineNamedVariableListRequest(
            name=mms.VmdSpecificObjectName(identifier='x'),
            specification=[mms.NameVariableSpecification(
                name=mms.VmdSpecificObjectName(identifier='b'))]),
        mms.DefineNamedVariableListResponse()
    ), (
        mms.DeleteNamedVariableListRequest(
            names=[mms.VmdSpecificObjectName(identifier='x')]),
        mms.DeleteNamedVariableListResponse(matched=0, deleted=0)
    ), (
        mms.DeleteNamedVariableListRequest(
            names=[mms.VmdSpecificObjectName(identifier='x')]),
        mms.ErrorResponse(error_class=mms.ErrorClass.RESOURCE, value=0)
)])
async def test_request_response(server_factory, req, resp):
    request = req
    response = resp
    requests_received = []

    async def connection_cb(_):
        pass

    async def server_req_cb(connection, request):
        requests_received.append(request)
        return response

    async def client_req_cb(connection, request):
        pass

    async with server_factory(connection_cb, server_req_cb) as server:
        address = server.addresses[0]
        conn = await mms.connect(client_req_cb, address)
        received_status = await conn.send_confirmed(request)
        await conn.async_close()

    assert len(requests_received) == 1
    assert requests_received == [request]
    assert received_status == response


@pytest.mark.asyncio
@pytest.mark.timeout(2)
@pytest.mark.parametrize("msg", [
    mms.UnsolicitedStatusUnconfirmed(logical=1, physical=1),
    mms.EventNotificationUnconfirmed(
        enrollment=mms.VmdSpecificObjectName(identifier='x'),
        condition=mms.AaSpecificObjectName(identifier='y'),
        severity=0,
        time=None),
    mms.EventNotificationUnconfirmed(
        enrollment=mms.DomainSpecificObjectName(domain_id='x',
                                                item_id='y'),
        condition=mms.VmdSpecificObjectName(identifier='y'),
        severity=0,
        time=b'2020-7-2T12:00:00.000Z'),
    mms.InformationReportUnconfirmed(
        specification=mms.VmdSpecificObjectName(identifier='x'),
        data=[]),
    mms.InformationReportUnconfirmed(
        specification=[
            mms.AddressVariableSpecification(address=10),
            mms.InvalidatedVariableSpecification(),
            mms.NameVariableSpecification(
                mms.VmdSpecificObjectName(identifier='x')),
            mms.ScatteredAccessDescriptionVariableSpecification(
                specifications=[mms.InvalidatedVariableSpecification()]),
            mms.VariableDescriptionVariableSpecification(
                address=10, type_specification=mms.BooleanTypeDescription()),
            mms.VariableDescriptionVariableSpecification(
                address=10,
                type_specification=mms.VmdSpecificObjectName('x'))],
        data=[mms.ArrayData(elements=[mms.BooleanData(value=True),
                                      mms.BooleanData(value=False),
                                      mms.BooleanData(value=True)])])
])
async def test_unconfirmed(server_factory, msg):

    async def connection_cb(connection):
        connection.send_unconfirmed(msg)

    async def server_req_cb(connection, request):
        pass

    async def client_req_cb(connection, request):
        pass

    async with server_factory(connection_cb, server_req_cb) as server:
        address = server.addresses[0]
        conn = await mms.connect(client_req_cb, address)
        received_unconfirmed = await conn.receive_unconfirmed()
        await conn.async_close()

    assert msg == received_unconfirmed


@pytest.mark.asyncio
@pytest.mark.timeout(2)
async def test_request_client(server_factory):

    expected_response = mms.IdentifyResponse(vendor='x',
                                             model='y',
                                             revision='z',
                                             syntaxes=None)
    connected_clients = []
    connection_cb_future = asyncio.Future()

    async def connection_cb(connection):
        connected_clients.append(
            await connection.send_confirmed(mms.IdentifyRequest()))
        connection_cb_future.set_result(True)

    async def server_req_cb(connection, request):
        pass

    async def client_req_cb(connection, request):
        return expected_response

    async with server_factory(connection_cb, server_req_cb) as server:
        address = server.addresses[0]
        await mms.connect(client_req_cb, address)
        await connection_cb_future

    assert connected_clients == [expected_response]


@pytest.mark.asyncio
@pytest.mark.timeout(2)
@pytest.mark.parametrize("type_description", [
    mms.ArrayTypeDescription(number_of_elements=10,
                             element_type=mms.VmdSpecificObjectName('x')),
    mms.BcdTypeDescription(xyz=1213),
    mms.BinaryTimeTypeDescription(xyz=True),
    mms.BitStringTypeDescription(xyz=1213),
    mms.BooleanTypeDescription(),
    mms.FloatingPointTypeDescription(format_width=12, exponent_width=10),
    mms.GeneralizedTimeTypeDescription(),
    mms.IntegerTypeDescription(xyz=345),
    mms.MmsStringTypeDescription(xyz=123),
    mms.ObjIdTypeDescription(),
    mms.OctetStringTypeDescription(xyz=1231),
    mms.StructureTypeDescription(components=[
        ('1', mms.ObjIdTypeDescription()),
        (None, mms.BooleanTypeDescription()),
        (None, mms.VmdSpecificObjectName('x')),
    ]),
    mms.UnsignedTypeDescription(xyz=21412),
    mms.UtcTimeTypeDescription(),
    mms.VisibleStringTypeDescription(xyz=5542),
])
async def test_type_description_serialization(server_factory,
                                              type_description):
    read_request = mms.GetVariableAccessAttributesRequest(value='x')
    expected_response = mms.GetVariableAccessAttributesResponse(
        mms_deletable=True, type_description=type_description)

    async def connection_cb(connection):
        pass

    async def server_req_cb(connection, request):
        assert request == read_request
        return expected_response

    async def client_req_cb(connection, request):
        pass

    async with server_factory(connection_cb, server_req_cb) as server:
        address = server.addresses[0]
        conn = await mms.connect(client_req_cb, address)
        read_response = await conn.send_confirmed(read_request)
        await conn.async_close()

    assert read_response == expected_response


@pytest.mark.asyncio
@pytest.mark.timeout(2)
@pytest.mark.parametrize("data", [
    [mms.BcdData(10)],
    [mms.ArrayData([mms.BcdData(11), mms.BcdData(12)])],
    [mms.BinaryTimeData(datetime.utcnow().replace(microsecond=0,
                                                  tzinfo=timezone.utc))],
    [mms.BitStringData([True, False, True])],
    [mms.BooleanData(True)],
    [mms.BooleanArrayData([True, False])],
    [mms.FloatingPointData(1.25)],
    [mms.GeneralizedTimeData('19851106210627.3')],
    [mms.IntegerData(100)],
    [mms.MmsStringData('abcxyz')],
    [mms.ObjIdData([0, 1, 1, 4, 1203])],
    [mms.OctetStringData(b'34104332')],
    [mms.StructureData([mms.MmsStringData('xyz'),
                        mms.IntegerData(321412)])],
    [mms.UnsignedData(123)],
    [mms.UtcTimeData(value=datetime.now(timezone.utc),
                     leap_second=False,
                     clock_failure=False,
                     not_synchronized=False,
                     accuracy=None)],
    [mms.VisibleStringData('123')],
])
async def test_data_serialization(server_factory, data):
    read_request = mms.ReadRequest(mms.AaSpecificObjectName('x'))
    expected_response = mms.ReadResponse(data)

    async def connection_cb(connection):
        pass

    async def server_req_cb(connection, request):
        assert request == read_request
        return expected_response

    async def client_req_cb(connection, request):
        pass

    async with server_factory(connection_cb, server_req_cb) as server:
        address = server.addresses[0]
        conn = await mms.connect(client_req_cb, address)
        read_response = await conn.send_confirmed(read_request)
        await conn.async_close()

    assert isinstance(read_response, mms.ReadResponse)
    for received_data, expected_data in zip(read_response.results,
                                            expected_response.results):
        if isinstance(received_data, mms.FloatingPointData):
            assert isinstance(data[0], mms.FloatingPointData)
            assert math.isclose(received_data.value, data[0].value)
        else:
            assert received_data == expected_data


@pytest.mark.asyncio
async def test_receive_unconfirmed_raises_connection_exception(server_factory):

    async def connection_cb(connection):
        pass

    async def request_cb(connection, request):
        pass

    async with server_factory(connection_cb, request_cb) as server:
        address = server.addresses[0]
        conn = await mms.connect(request_cb, address)
        result_future = conn.receive_unconfirmed()

    with pytest.raises(ConnectionError):
        await result_future

    await conn.async_close()


@pytest.mark.asyncio
async def test_send_confirmed_raises_connection_exception(server_factory):

    async def connection_cb(connection):
        pass

    async def request_cb(connection, request):
        await asyncio.sleep(1)

    async with server_factory(connection_cb, request_cb) as server:
        address = server.addresses[0]
        conn = await mms.connect(request_cb, address)
        result_future = conn.send_confirmed(mms.StatusRequest())

    with pytest.raises(ConnectionError):
        await result_future

    await conn.async_close()

    async with server_factory(connection_cb, request_cb) as server:
        address = server.addresses[0]
        conn = await mms.connect(request_cb, address)
        result_future = asyncio.ensure_future(
            conn.send_confirmed(mms.StatusRequest()))
        await asyncio.sleep(0.01)

    with pytest.raises(ConnectionError):
        await result_future

    await conn.async_close()
