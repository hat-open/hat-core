import asyncio
import contextlib
import pytest

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
        await asyncio.wait([server.async_close(),
                            *(conn.async_close() for conn in connections)])

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

    await asyncio.wait([conn.async_close() for conn in client_connections])


@pytest.mark.asyncio
@pytest.mark.timeout(10)
@pytest.mark.parametrize("req,resp", [
    (mms.StatusRequest(), mms.StatusResponse(logical=1, physical=1)),
    (mms.GetNameListRequest(object_class=mms.ObjectClass.NAMED_VARIABLE,
                            object_scope=mms.VmdSpecificObjectScope(),
                            continue_after=None),
     mms.GetNameListResponse(identifiers=['a', 'b', 'c'],
                             more_follows=False)),
    (mms.IdentifyRequest(),
     mms.IdentifyResponse(vendor='a', model='b', revision='c', syntaxes=None)),
    (mms.IdentifyRequest(),
     mms.IdentifyResponse(vendor='a', model='b', revision='c',
                          syntaxes=[[2, 1, 3], [3, 6, 5]])),
    (mms.GetVariableAccessAttributesRequest(value='x'),
     mms.GetVariableAccessAttributesResponse(
        mms_deletable=True, type_description=mms.BooleanTypeDescription())),
    (mms.GetVariableAccessAttributesRequest(
        value=mms.VmdSpecificObjectName(identifier='x')),
     mms.GetVariableAccessAttributesResponse(
        mms_deletable=True, type_description=mms.BooleanTypeDescription())),
    (mms.ReadRequest(value=mms.VmdSpecificObjectName(identifier='x')),
     mms.ReadResponse(results=[mms.BooleanData(value=True)])),
    (mms.ReadRequest(value=mms.VmdSpecificObjectName(identifier='x')),
     mms.ReadResponse(results=[mms.DataAccessError.INVALID_ADDRESS])),
    (mms.WriteRequest(specification=mms.VmdSpecificObjectName(identifier='x'),
                      data=[mms.BooleanData(value=True)]),
     mms.WriteResponse(results=[mms.DataAccessError.INVALID_ADDRESS])),
    (mms.DefineNamedVariableListRequest(
        name=mms.VmdSpecificObjectName(identifier='x'),
        specification=[mms.NameVariableSpecification(
            name=mms.VmdSpecificObjectName(identifier='x'))]),
     mms.DefineNamedVariableListResponse()),
    (mms.DeleteNamedVariableListRequest(
        names=[mms.VmdSpecificObjectName(identifier='x')]),
     mms.DeleteNamedVariableListResponse(matched=0, deleted=0)),
    (mms.DeleteNamedVariableListRequest(
        names=[mms.VmdSpecificObjectName(identifier='x')]),
     mms.ErrorResponse(error_class=mms.ErrorClass.RESOURCE, value=0))
])
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

    assert len(requests_received) == 1
    assert requests_received == [request]
    assert received_status == response

    await conn.async_close()


@pytest.mark.asyncio
@pytest.mark.timeout(2)
@pytest.mark.parametrize("msg", [
    mms.UnsolicitedStatusUnconfirmed(logical=1, physical=1),
    mms.EventNotificationUnconfirmed(
        enrollment=mms.VmdSpecificObjectName(identifier='x'),
        condition=mms.AaSpecificObjectName(identifier='y'),
        severity=0,
        time=None),
    # mms.EventNotificationUnconfirmed(
    #     enrollment=mms.DomainSpecificObjectName(domain_id='x',
    #                                             item_id='y'),
    #     condition=mms.VmdSpecificObjectName(identifier='y'),
    #     severity=0,
    #     time='2020-7-2T12:00:00.000Z'),
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
                address=10, type_specification=mms.BooleanTypeDescription())],
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
