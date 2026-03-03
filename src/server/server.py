import asyncio
import time

from proto import BasePackage
from proto.network import receive_package, send_package
from proto.packages import PingRequest


class ServerClient:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer

    async def process_request(self, packet: BasePackage):
        if isinstance(packet, PingRequest):
            response = PingRequest(
                request_id=packet.request_id, timestamp=time.time_ns()
            )
            await send_package(response, self.writer)

    async def loop_read(self):
        while True:
            try:
                package = await receive_package(self.reader)
                await self.process_request(package)

            except asyncio.IncompleteReadError:
                print("Client disconnected")
                break


class Server:
    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self.server: asyncio.AbstractServer | None = None
        self.clients: list[ServerClient] = []

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        client = ServerClient(reader, writer)
        self.clients.append(client)
        await client.loop_read()

    async def serve(self):
        self.server = await asyncio.start_server(
            self.handle_client, host=self.host, port=self.port
        )
        async with self.server:
            print(f"Server started on {self.host}:{self.port}")
            await self.server.serve_forever()

    def run_loop(self):
        asyncio.run(self.serve())
