import asyncio
import logging
import signal
import ssl
from typing import Awaitable, Callable

from proto import Cryptography, HandlerType

from .client import ServerClient

logger = logging.getLogger(__name__)


class Server:
    def __init__(
        self,
        host: str,
        port: int,
        mnemonic: str,
        handler: HandlerType,
        ssl_ctx: ssl.SSLContext,
        on_startup: Callable[[], Awaitable[None]] | None = None,
        on_shutdown: Callable[[], Awaitable[None]] | None = None,
    ):
        self.host = host
        self.port = port
        self.crypto = Cryptography(mnemonic)

        self._handler = handler
        self._clients: dict[bytes, ServerClient] = {}
        self._server_clients: dict[bytes, ServerClient] = {}

        self.ssl_ctx = ssl_ctx
        self.on_startup = on_startup
        self.on_shutdown = on_shutdown

    async def connect_to_server(
        self, host: str, port: int, ssl_ctx: ssl.SSLContext | None = None
    ) -> ServerClient:
        if ssl_ctx is not None:
            reader, writer = await asyncio.open_connection(host, port, ssl=ssl_ctx)
        else:
            reader, writer = await asyncio.open_connection(host, port)
        peer = writer.get_extra_info("peername")
        sockname = writer.get_extra_info("sockname")
        logger.info("Connected to server %s -> %s", sockname, peer)

        client = ServerClient(
            reader=reader,
            writer=writer,
            crypto=self.crypto,
            handler=self._handler,
        )
        client._create_loop(client._ping_client())
        return client

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        peer = writer.get_extra_info("peername")
        sockname = writer.get_extra_info("sockname")
        logger.info("New client connected from %s -> %s", peer, sockname)
        client = ServerClient(
            reader=reader,
            writer=writer,
            crypto=self.crypto,
            handler=self._handler,
        )
        client._create_loop(client._ping_client())
        try:
            await client.wait_loop()
        finally:
            client.disconnect()
            for public_key in client.remote_public_keys:
                self._clients.pop(public_key, None)
            client.remote_public_keys.clear()
            logger.info("Client disconnected %s", peer)

    def register_client_pub_keys(self, client: ServerClient):
        for public_key in client.remote_public_keys:
            self._clients[public_key] = client

    def get_client_by_pub_key(self, public_key: bytes) -> ServerClient | None:
        return self._clients.get(public_key)

    async def serve(self):
        loop = asyncio.get_running_loop()

        # Call on_startup if provided
        if self.on_startup:
            await self.on_startup()

        server = await asyncio.start_server(
            self.handle_client, self.host, self.port, ssl=self.ssl_ctx
        )
        logger.info(f"Server started on {self.host}:{self.port}")

        # Setup signal handlers for graceful shutdown
        def shutdown():
            logger.info("Shutting down server...")
            server.close()

        loop.add_signal_handler(signal.SIGINT, shutdown)
        loop.add_signal_handler(signal.SIGTERM, shutdown)

        async with server:
            await server.serve_forever()

        # Call on_shutdown if provided
        if self.on_shutdown:
            await self.on_shutdown()

    def run_loop(self):
        asyncio.run(self.serve())
