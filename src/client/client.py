import asyncio
import os
from typing import Any, cast
import uuid

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from ecdsa import SECP256k1, SigningKey, VerifyingKey
from mnemonic import Mnemonic

from proto import TYPES_TO_CLASSES, RequestProto, receive_package, send_package


class ClientCryptography:
    def __init__(self, mnemonic_phrase: str):
        mnemonic = Mnemonic("english")
        seed = mnemonic.to_seed(mnemonic_phrase)

        priv = seed[:32]
        sk = SigningKey.from_string(priv, curve=SECP256k1)
        vk = cast(VerifyingKey, sk.verifying_key)
        self.private_key = priv.hex()
        self.public_key = vk.to_string("compressed").hex()

    def encrypt_message(self, to_addr: str, payload: bytes) -> bytes:
        recipient_public = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256K1(), bytes.fromhex(to_addr)
        )

        ephemeral_priv = ec.generate_private_key(ec.SECP256K1())
        shared = ephemeral_priv.exchange(ec.ECDH(), recipient_public)

        key = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None, info=b"ecies"
        ).derive(shared)

        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, payload, None)

        eph_pub = ephemeral_priv.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.CompressedPoint,
        )
        return eph_pub + nonce + ct

    def sign_message(self, message: bytes) -> str:
        sk = SigningKey.from_string(self.private_key, curve=SECP256k1)
        signature = sk.sign(message)
        return signature.hex()


class Client:
    def __init__(self, host: str, port: int, mnemonic: str):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.awaited_requests: dict[uuid.UUID, asyncio.Future] = {}

        self.crypto = ClientCryptography(mnemonic)

        self._loop = None

    async def _request(self, package: RequestProto) -> Any:
        if not self.writer:
            raise RuntimeError("Not connected")

        future = asyncio.get_event_loop().create_future()
        self.awaited_requests[package.request_id] = future

        await send_package(package, self.writer)
        result = await future

        return result

    async def _loop_read(self):
        if not self.reader or not self.writer:
            raise RuntimeError("Not connected")

        while True:
            try:
                package = await receive_package(self.reader)
                package_data = cast(RequestProto, package)

                future = self.awaited_requests.pop(package_data.request_id, None)
                if future is not None and not future.done():
                    future.set_result(package)

            except asyncio.IncompleteReadError:
                print("Server disconnected")
                break

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        self._loop = asyncio.create_task(self._loop_read())
