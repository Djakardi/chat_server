from storage import StorageConnection

from .dispatcher import server_dp
from .server import Server
from .settings import Settings


async def run_server(settings: Settings | None = None):
    if settings is None:
        settings = Settings()  # pyright: ignore[reportCallIssue]

    storage_conn = StorageConnection(settings.REDIS_URL)
    server = Server(
        host=settings.HOST,
        port_plaintext=settings.PORT,
        mnemonic=settings.MNEMONIC_SERVER,
        handler=server_dp,
    )
    server_dp.context["server"] = server
    server_dp.context["storage_conn"] = storage_conn
    await server.serve()
