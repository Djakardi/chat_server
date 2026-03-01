import asyncio


class Server:
    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self.server: asyncio.AbstractServer | None = None

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        pass

    async def serve(self):
        self.server = await asyncio.start_server(
            self.handle_client, host=self.host, port=self.port
        )

    def run_loop(self):
        asyncio.run(self.serve())
