from .connection import StorageConnection


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
