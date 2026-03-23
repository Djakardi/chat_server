import asyncio
import logging
import ssl

from proto import BaseProtoClient, Cryptography
from proto.packages import PingRequest, MessageRequest, MessageResponse

logger = logging.getLogger(__name__)


class Client(BaseProtoClient):
    async def _loop_ping(self):
        while True:
            try:
                ping_time = await self.ping()
                logger.info(f"Ping: {ping_time} ms")
            except TimeoutError:
                self.disconnect()
                logger.warning("Connection lost")
                break

            await asyncio.sleep(5)

    @classmethod
    async def connect(
        cls,
        host: str,
        port: int,
        mnemonic: str,
        *,
        ssl_ctx: ssl.SSLContext | None = None,
        server_hostname: str | None = None,
    ):
        # Pass ssl context to asyncio.open_connection when provided.
        # If ssl_ctx is None, connection will be plaintext.
        if ssl_ctx is not None:
            reader, writer = await asyncio.open_connection(
                host, port, ssl=ssl_ctx, server_hostname=server_hostname
            )
        else:
            reader, writer = await asyncio.open_connection(host, port)

        client = cls(
            reader=reader,
            writer=writer,
            crypto=Cryptography(mnemonic),
            handler=None,
        )
        client._create_loop(client._loop_ping())
        return client

    async def ping(self) -> float:
        request = PingRequest(from_addr=bytes.fromhex(self.crypto.public_key))
        response = await self._request(request, PingRequest)
        return round((response.timestamp - request.timestamp) / 1e9, 2)

    async def send_message(self, to_addr: str, payload: bytes) -> None:
        request = MessageRequest(
            from_addr=bytes.fromhex(self.crypto.public_key),
            to_addr=bytes.fromhex(to_addr),
            payload=self.crypto.encrypt_message(to_addr, payload),
        )
        await self._request(request, MessageResponse)
