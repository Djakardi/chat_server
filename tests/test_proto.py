import asyncio
import uuid

import pytest

from proto.base import var_to_bytes, bytes_to_var
from proto.network import _read_package_type, send_package, receive_package
from proto.packages import PingRequest


def test_var_serialization():
    # int
    b = var_to_bytes(300, int)
    # should be length prefix + big-endian
    assert b[0] == 2
    assert int.from_bytes(b[1:], "big") == 300
    assert bytes_to_var(b[1:], int) == 300

    # uuid
    u = uuid.uuid4()
    b = var_to_bytes(u, uuid.UUID)
    assert b[0] == 16
    assert bytes_to_var(b[1:], uuid.UUID) == u


def test_package_roundtrip():
    req = PingRequest(request_id=uuid.uuid4(), timestamp=12345678)
    data = req.to_bytes()
    # parse type from data, should be 2 (PING_V1)
    assert _read_package_type(data) == PingRequest.type
    restored = PingRequest.from_bytes(data)
    assert restored == req


@pytest.mark.asyncio
async def test_network_send_receive(tmp_path):
    """Start a temporary server that echoes back whatever is received."""

    async def handler(reader, writer):
        pkt = await receive_package(reader)
        # echo the same packet
        await send_package(pkt, writer)
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    req = PingRequest(request_id=uuid.uuid4(), timestamp=42)
    await send_package(req, writer)
    resp = await receive_package(reader)
    assert isinstance(resp, PingRequest)
    assert resp.request_id == req.request_id
    server.close()
    await server.wait_closed()
