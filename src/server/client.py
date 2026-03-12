import asyncio
import logging

from proto import BaseProtoClient, Cryptography, HandlerType
from proto.packages import PingRequest


logger = logging.getLogger(__name__)


class ServerClient(BaseProtoClient):
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        crypto: Cryptography,
        handler: HandlerType,
    ):
        super().__init__(reader=reader, writer=writer, crypto=crypto, handler=handler)
        self.remote_public_keys: set[bytes] = set()

    async def _ping_client(self):
        if not self.remote_public_keys:
            self.remote_public_keys = set()

        while True:
            try:
                ping_time = await self.ping()
                logger.info("Client ping: %s ms", ping_time)
            except TimeoutError:
                self.disconnect()
                logger.warning("Client connection lost")
                break

            await asyncio.sleep(5)

    async def ping(self) -> float:
        request = PingRequest(from_addr=bytes.fromhex(self.crypto.public_key))
        response = await self._request(request, PingRequest)
        return round((response.timestamp - request.timestamp) / 1e9, 2)
