from redis.asyncio import ConnectionPool, Redis


class StorageConnection:
    def __init__(self, url: str):
        self.connection_pool = ConnectionPool.from_url(url)

    def get_session(self):
        return Redis.from_pool(self.connection_pool)
