from .client import Client
from .dispatcher import client_dp


async def run_client(host: str, port: int, mnemonic: str):
    client = await Client.connect(host=host, port=port, mnemonic=mnemonic)
    client.setup_handler(client_dp)

    await client.wait_loop()


__all__ = ["run_client"]
