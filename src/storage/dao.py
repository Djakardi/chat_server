import json

from .connection import StorageConnection
from .models import ServerInfo


MESSAGES_TTL = 7 * 24 * 3600  # 7 days
MAX_MESSAGES_PER_ADDR = 1000


class DAO:
    def __init__(self, connection: StorageConnection):
        self.session = connection.get_session()

    async def __aenter__(self) -> "DAO":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.aclose()

    async def save_message(self, to_addr: str, packet_data: bytes):
        key = f"messages:{to_addr}"
        async with self.session.pipeline(transaction=True) as pipe:
            pipe.rpush(key, packet_data)
            pipe.ltrim(key, -MAX_MESSAGES_PER_ADDR, -1)
            pipe.expire(key, MESSAGES_TTL)
            await pipe.execute()

    async def peek_message(self, to_addr: str) -> bytes | None:
        return await self.session.lindex(
            f"messages:{to_addr}", 0
        )  # pyright: ignore[reportReturnType]

    async def pop_message(self, to_addr: str) -> bytes | None:
        return await self.session.lpop(
            f"messages:{to_addr}"
        )  # pyright: ignore[reportReturnType]

    async def get_messages_for_addr(self, to_addr: str) -> list[bytes]:
        return await self.session.lrange(f"messages:{to_addr}", 0, -1)

    async def clear_messages_for_addr(self, to_addr: str):
        await self.session.delete(f"messages:{to_addr}")

    async def append_server_info(self, server_info: ServerInfo):
        data = server_info.__dict__.copy()
        data["server_public_key"] = data["server_public_key"].hex()
        await self.session.sadd("servers_info", json.dumps(data))

    async def get_all_server_info(self) -> list[ServerInfo]:
        server_info_jsons = await self.session.smembers("servers_info")
        infos = []
        for info_json in server_info_jsons:
            data = json.loads(info_json)
            data["server_public_key"] = bytes.fromhex(data["server_public_key"])
            infos.append(ServerInfo(**data))
        return infos

    async def clear_all(self):
        await self.session.flushdb()
