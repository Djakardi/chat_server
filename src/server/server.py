import asyncio
import logging
import ssl

from proto import Cryptography, HandlerType

from .client import ServerClient

logger = logging.getLogger(__name__)


class Server:
    def __init__(
        self,
        host: str,
        mnemonic: str,
        handler: HandlerType,
        *,
        port_plaintext: int | None = None,
        port_ssl: int | None = None,
        ssl_ctx: ssl.SSLContext | None = None,
        run_only_ssl: bool = False,
        run_only_plaintext: bool = False,
    ):
        if run_only_ssl and run_only_plaintext:
            raise ValueError("Cannot run with both SSL and plaintext only")
        if run_only_ssl and ssl_ctx is None:
            raise ValueError("SSL context must be provided when run_only_ssl is True")

        if not run_only_ssl and port_plaintext is None:
            raise ValueError(
                "Port for plaintext must be provided when not running only SSL"
            )
        if not run_only_plaintext and port_ssl is None:
            raise ValueError(
                "Port for SSL must be provided when not running only plaintext"
            )

        self.host = host
        self.port_ssl = port_ssl
        self.port_plaintext = port_plaintext
        self.crypto = Cryptography(mnemonic)

        self._handler = handler
        self._servers: list[asyncio.AbstractServer] = []
        self._clients: dict[bytes, ServerClient] = {}

        self.ssl_ctx = ssl_ctx
        self.run_plaintext = not run_only_ssl
        self.run_ssl = not run_only_plaintext

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
        if self.run_plaintext:
            server = await asyncio.start_server(
                self.handle_client, self.host, self.port_plaintext
            )
            self._servers.append(server)
            logger.info(
                f"Server started on {self.host}:{self.port_plaintext} (plaintext)"
            )
        if self.run_ssl and self.ssl_ctx:
            server_ssl = await asyncio.start_server(
                self.handle_client, self.host, self.port_ssl, ssl=self.ssl_ctx
            )
            self._servers.append(server_ssl)
            logger.info(f"Server started on {self.host}:{self.port_ssl} (SSL)")

    def run_loop(self):
        asyncio.run(self.serve())
