from storage import StorageConnection

from .dispatcher import server_dp
from .server import Server
from .settings import Settings


async def run_server(settings: Settings | None = None):
    if settings is None:
        settings = Settings()  # pyright: ignore[reportCallIssue]

    storage_conn = StorageConnection(settings.REDIS_URL)
    
    # Устанавливаем порты по умолчанию, если они не указаны
    port_plaintext = settings.PORT_PLAINTEXT
    port_ssl = settings.PORT_SSL
    
    if settings.RUN_ONLY_PLAINTEXT and port_plaintext is None:
        port_plaintext = 8080
    if settings.RUN_ONLY_SSL and port_ssl is None:
        port_ssl = 8443
    if not settings.RUN_ONLY_PLAINTEXT and not settings.RUN_ONLY_SSL:
        if port_plaintext is None:
            port_plaintext = 8080
        if port_ssl is None:
            port_ssl = 8443
    
    ssl_ctx = settings.get_ssl_context()
    
    server = Server(
        host=settings.HOST,
        mnemonic=settings.MNEMONIC_SERVER,
        handler=server_dp,
        port_plaintext=port_plaintext,
        port_ssl=port_ssl,
        ssl_ctx=ssl_ctx,
        run_only_ssl=settings.RUN_ONLY_SSL,
        run_only_plaintext=settings.RUN_ONLY_PLAINTEXT,
    )
    server_dp.context["server"] = server
    server_dp.context["storage_conn"] = storage_conn
    await server.serve()
