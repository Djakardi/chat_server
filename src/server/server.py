import asyncio
import logging

from proto import Cryptography, HandlerType

from .client import ServerClient

logger = logging.getLogger(__name__)


class Server:
    def __init__(self, host: str, port: int, mnemonic: str, handler: HandlerType):
        self.host = host
        self.port = port
        self.crypto = Cryptography(mnemonic)

        self._handler = handler
        self._server: asyncio.AbstractServer | None = None
        self._clients: dict[bytes, ServerClient] = {}

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        logger.info("New client connected")
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
            logger.info("Client disconnected")

    def register_client_pub_keys(self, client: ServerClient):
        for public_key in client.remote_public_keys:
            self._clients[public_key] = client

    def get_client_by_pub_key(self, public_key: bytes) -> ServerClient | None:
        return self._clients.get(public_key)

    async def serve(self):
        self._server = await asyncio.start_server(
            self.handle_client, host=self.host, port=self.port
        )
        async with self._server:
            logger.info(f"Server started on {self.host}:{self.port}")
            await self._server.serve_forever()

    def run_loop(self):
        asyncio.run(self.serve())
