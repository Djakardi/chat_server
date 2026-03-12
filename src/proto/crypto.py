import os
from typing import cast

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from ecdsa import SECP256k1, SigningKey, VerifyingKey
from mnemonic import Mnemonic

from proto.base import BasePackage


class Cryptography:
    def __init__(self, mnemonic_phrase: str):
        mnemonic = Mnemonic("english")
        seed = mnemonic.to_seed(mnemonic_phrase)

        priv = seed[:32]
        sk = SigningKey.from_string(priv, curve=SECP256k1)
        vk = cast(VerifyingKey, sk.verifying_key)

        self._private_key = priv.hex()
        self.public_key_bytes = vk.to_string("compressed")
        self.public_key: str = self.public_key_bytes.hex()

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

    def decrypt_message(self, payload: bytes) -> bytes:
        eph_pub_bytes = payload[:33]
        nonce = payload[33:45]
        ct = payload[45:]

        eph_pub = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256K1(), eph_pub_bytes
        )

        priv_int = int.from_bytes(bytes.fromhex(self._private_key), byteorder="big")
        private_key = ec.derive_private_key(priv_int, ec.SECP256K1())

        shared = private_key.exchange(ec.ECDH(), eph_pub)

        key = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None, info=b"ecies"
        ).derive(shared)

        return AESGCM(key).decrypt(nonce, ct, None)

    def sign_package(self, package: BasePackage) -> BasePackage:
        if package.from_addr != self.public_key_bytes:
            raise ValueError("Package from_addr does not match public key")

        sk = SigningKey.from_string(bytes.fromhex(self._private_key), curve=SECP256k1)
        return package.sign_package(sk.sign(package.to_bytes(exclude_signature=True)))

    @staticmethod
    def verify_signature(package: BasePackage) -> bool:
        vk = VerifyingKey.from_string(package.from_addr, curve=SECP256k1)
        try:
            vk.verify(package.signature, package.to_bytes(exclude_signature=True))
            return True
        except Exception:
            return False
