import logging

from proto import Cryptography
from proto.packages import PingRequest

logger = logging.getLogger(__name__)


def test_crypto():
    mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
    crypto = Cryptography(mnemonic)
    logger.info("Public Key: %s", crypto.public_key)
    logger.info("Private Key: %s", crypto._private_key)

    package = PingRequest(from_addr=bytes.fromhex(crypto.public_key))
    logger.info("Data to sign: %s", package.to_bytes(exclude_signature=True).hex())
    signed_package = crypto.sign_package(package)
    logger.info("Signature: %s", signed_package.signature.hex())

    is_verified = Cryptography.verify_signature(signed_package)
    if is_verified:
        logger.info("Signature verified successfully!")
    else:
        logger.error("Signature verification failed!")


if __name__ == "__main__":
    test_crypto()
