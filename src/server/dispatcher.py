import asyncio
import logging
import ssl

from dispatcher import Dispatcher

from proto.packages import (
    PingRequest,
    MessageRequest,
    MessageResponse,
    ServerInfoRequest,
    UserLookupRequest,
    UserLookupResponse,
    ForwardedMessageRequest,
    ForwardedMessageResponse,
)
from server.settings import Settings
from storage import StorageConnection, DAO, ServerInfo

from .client import ServerClient
from .server import Server


server_dp = Dispatcher()
logger = logging.getLogger(__name__)


async def on_startup(
    server: Server, settings: Settings, storage_conn: StorageConnection
):
    logger.info("Server is starting up...")
    async with DAO(storage_conn) as dao:
        servers = await dao.get_all_server_info()

    for info in servers:
        try:
            client = await server.connect_to_server(
                host=info.server_ip, port=info.server_port
            )
            server._server_clients[info.server_public_key] = client
            # Send our info to the connected server
            info_req = ServerInfoRequest(
                from_addr=server.crypto.public_key_bytes,
                server_ip=settings.PUBLIC_HOST,
                server_port=settings.PUBLIC_PORT,
                server_public_key=server.crypto.public_key_bytes,
            )
            await client.proxy_request(info_req, return_type=ServerInfoRequest)
            logger.info("Connected to server %s:%d", info.server_ip, info.server_port)
        except Exception as e:
            logger.warning(
                "Failed to connect to server %s:%d: %s",
                info.server_ip,
                info.server_port,
                e,
            )

    logger.info("Startup complete.")


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
        logger.warning(
            "Destination client not found locally for request_id: %s",
            package.request_id,
        )

        # Try to find on other servers
        for server_client in server._server_clients.values():
            try:
                lookup_req = UserLookupRequest(
                    from_addr=server.crypto.public_key_bytes,
                    user_addr=package.to_addr,
                )
                lookup_resp = await server_client.proxy_request(
                    lookup_req, return_type=UserLookupResponse
                )
                if lookup_resp.is_reachable:
                    # Forward the message
                    forward_req = ForwardedMessageRequest(
                        from_addr=server.crypto.public_key_bytes,
                        original_message_bytes=package.to_bytes(),
                    )
                    forward_resp = await server_client.proxy_request(
                        forward_req, return_type=ForwardedMessageResponse
                    )
                    if forward_resp.is_delivered:
                        return MessageResponse(
                            request_id=package.request_id,
                            from_addr=client.crypto.public_key_bytes,
                            is_delivered=True,
                        )
                    else:
                        logger.warning(
                            "Forwarding failed for request_id: %s", package.request_id
                        )
                        break  # Stop trying other servers
            except Exception as e:
                logger.warning("Failed to query or forward to server: %s", e)
                continue

    # If not delivered, store offline
    async with DAO(storage_conn) as dao:
        await dao.save_message(
            to_addr=package.to_addr.hex(), packet_data=package.to_bytes()
        )

    return MessageResponse(
        request_id=package.request_id,
        from_addr=client.crypto.public_key_bytes,
        is_delivered=False,
    )


@server_dp.register(ServerInfoRequest)
async def server_info(
    package: ServerInfoRequest,
    client: ServerClient,
    server: Server,
    settings: Settings,
    storage_conn: StorageConnection,
):
    # Register the connecting server
    server._server_clients[package.server_public_key] = client

    async with DAO(storage_conn) as dao:
        await dao.append_server_info(
            ServerInfo(
                server_ip=package.server_ip,
                server_port=package.server_port,
                server_public_key=package.server_public_key,
            )
        )

    return ServerInfoRequest(
        server_ip=settings.PUBLIC_HOST,
        server_port=settings.PUBLIC_PORT,
        server_public_key=server.crypto.public_key_bytes,
    )


@server_dp.register(UserLookupRequest)
async def user_lookup(
    package: UserLookupRequest,
    server: Server,
):
    is_reachable = server.get_client_by_pub_key(package.user_addr) is not None
    return UserLookupResponse(
        request_id=package.request_id,
        from_addr=server.crypto.public_key_bytes,
        is_reachable=is_reachable,
    )


@server_dp.register(ForwardedMessageRequest)
async def forward_message(
    package: ForwardedMessageRequest,
    client: ServerClient,
    server: Server,
    storage_conn: StorageConnection,
):
    # Deserialize the original message
    try:
        original_msg = MessageRequest.from_bytes(package.original_message_bytes)
    except Exception as e:
        logger.error("Failed to deserialize forwarded message: %s", e)
        return ForwardedMessageResponse(
            request_id=package.request_id,
            from_addr=server.crypto.public_key_bytes,
            is_delivered=False,
        )

    # Verify the original message signature
    if not server.crypto.verify_signature(original_msg):
        logger.warning("Invalid signature on forwarded message")
        return ForwardedMessageResponse(
            request_id=package.request_id,
            from_addr=server.crypto.public_key_bytes,
            is_delivered=False,
        )

    # Now route the original message as if it came directly
    # But since it's forwarded, the client is the forwarding server, but we need to treat it as from the original sender
    # Actually, in route_message, it uses client for registering keys, but for forwarded, perhaps don't register again
    # To simplify, call route_message with the original_msg, but adjust client if needed
    # For now, since route_message registers keys from client, but for forwarded, the keys are from original
    # Perhaps create a dummy client or adjust

    # Actually, better to duplicate the logic without registering keys again, since it's already done on the original server

    dest_client = server.get_client_by_pub_key(original_msg.to_addr)
    if dest_client:
        try:
            response = await dest_client.proxy_request(
                original_msg, return_type=MessageResponse
            )
            return ForwardedMessageResponse(
                request_id=package.request_id,
                from_addr=server.crypto.public_key_bytes,
                is_delivered=response.is_delivered,
            )
        except Exception as e:
            logger.error("Failed to deliver forwarded message: %s", e)

    # If not delivered, store offline
    async with DAO(storage_conn) as dao:
        await dao.save_message(
            to_addr=original_msg.to_addr.hex(), packet_data=original_msg.to_bytes()
        )

    return ForwardedMessageResponse(
        request_id=package.request_id,
        from_addr=server.crypto.public_key_bytes,
        is_delivered=False,
    )
