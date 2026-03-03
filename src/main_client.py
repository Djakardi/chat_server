import asyncio
import os
import time
import uuid

from client import Client
from proto.packages import PingRequest


async def main():
    mnemonic = os.getenv("MNEMONIC")
    if not mnemonic:
        print("Please set the MNEMONIC environment variable")
        return

    client = Client("localhost", 8080, mnemonic)
    await client.connect()

    request = PingRequest(request_id=uuid.uuid4(), timestamp=time.time_ns())

    print("Sending ping:", request)
    print("Ping result:", await client._request(request))

    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
