import asyncio
import logging

from dispatcher import Dispatcher

from proto.packages import PingRequest, MessageRequest, MessageResponse
from storage import StorageConnection, DAO

from .client import ServerClient
from .server import Server


server_dp = Dispatcher()
logger = logging.getLogger(__name__)


async def _drain_offline(
    client: ServerClient, addr: bytes, storage_conn: StorageConnection
):
    async with DAO(storage_conn) as dao:
        while True:
            raw = await dao.peek_message(addr.hex())
            if raw is None:
                break

            try:
                msg = MessageRequest.from_bytes(raw)
                response = await client.proxy_request(msg, return_type=MessageResponse)
            except Exception as e:
                logger.warning("Drain interrupted for %s: %s", addr.hex(), e)
                break

            if not response.is_delivered:
                logger.warning(
                    "Client rejected message, stopping drain for %s", addr.hex()
                )
                break

            await dao.pop_message(addr.hex())


@server_dp.register(PingRequest)
async def ping(
    package: PingRequest,
    client: ServerClient,
    server: Server,
    storage_conn: StorageConnection,
):
    client.remote_public_keys.add(package.from_addr)
    server.register_client_pub_keys(client)

    asyncio.create_task(_drain_offline(client, package.from_addr, storage_conn))

    return PingRequest(
        request_id=package.request_id, from_addr=client.crypto.public_key_bytes
    )


@server_dp.register(MessageRequest)
async def route_message(
    package: MessageRequest,
    client: ServerClient,
    server: Server,
    storage_conn: StorageConnection,
):
    client.remote_public_keys.add(package.from_addr)
    server.register_client_pub_keys(client)

    dest_client = server.get_client_by_pub_key(package.to_addr)
    if dest_client:
        try:
            return await dest_client.proxy_request(package, return_type=MessageResponse)
        except Exception as e:
            logger.error("Failed to deliver message: %s", e)
    else:
        logger.warning("Destination client not found for request_id: %s", package.request_id)

    async with DAO(storage_conn) as dao:
        await dao.save_message(
            to_addr=package.to_addr.hex(), packet_data=package.to_bytes()
        )

    return MessageResponse(
        request_id=package.request_id,
        from_addr=client.crypto.public_key_bytes,
        is_delivered=False,
    )
