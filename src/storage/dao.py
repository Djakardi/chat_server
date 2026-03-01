from .connection import RedisConnection


class RedisDAO:
    def __init__(self, connection: RedisConnection):
        self.session = connection.get_session()

    async def __aenter__(self) -> "RedisDAO":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.aclose()
