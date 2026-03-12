from dispatcher import Dispatcher
from proto.packages import PingRequest, MessageRequest, MessageResponse

from .client import Client

client_dp = Dispatcher()


@client_dp.register(PingRequest)
async def ping(package: PingRequest, client: Client):
    return PingRequest(
        request_id=package.request_id, from_addr=client.crypto.public_key_bytes
    )


@client_dp.register(MessageRequest)
async def message(package: MessageRequest, client: Client):
    decrypted_message = client.crypto.decrypt_message(package.payload)
    print(
        f"Message from {package.from_addr.hex()}:\n"
        f"{decrypted_message.decode('utf-8')}\n---"
    )

    return MessageResponse(
        request_id=package.request_id,
        from_addr=client.crypto.public_key_bytes,
        is_delivered=True,
    )
