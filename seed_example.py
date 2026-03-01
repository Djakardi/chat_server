"""
seed_example.py

Generate a 24‑word BIP‑39 mnemonic (seed phrase) and turn it into a
private/public key pair (secp256k1).

This is just a demonstration and **not** production-ready code.

Requirements:
    pip install mnemonic ecdsa cryptography

Usage:
    python seed_example.py

"""

from mnemonic import Mnemonic
from ecdsa import SigningKey, VerifyingKey, SECP256k1


def generate_mnemonic(strength: int = 256) -> str:
    """Return a BIP‑39 mnemonic phrase.

    Args:
        strength: entropy strength in bits. 256 bits → 24-word phrase.
    """
    mnemo = Mnemonic("english")
    return mnemo.generate(strength=strength)


def mnemonic_to_seed(mnemonic: str, passphrase: str = "") -> bytes:
    """Derive the BIP‑39 seed from the mnemonic.

    The seed is normally used as input to a BIP‑32 master key derivation.
    Here we just treat the first 32 bytes as a private key for illustration.
    """
    mnemo = Mnemonic("english")
    return mnemo.to_seed(mnemonic, passphrase=passphrase)


def seed_to_keypair(seed: bytes) -> tuple[str, str]:
    """Derive a private/public keypair from the seed.

    This example simply uses the first 32 bytes of the seed as a raw
    secp256k1 private key.  No BIP‑32/BIP‑44 path derivation is shown.
    """
    # take 32 bytes, if seed is shorter pad or triplet, etc.
    priv = seed[:32]
    sk = SigningKey.from_string(priv, curve=SECP256k1)
    vk = sk.verifying_key
    # return hex-encoded strings
    return priv.hex(), vk.to_string("compressed").hex()


def sign_message(priv_hex: str, message: bytes) -> str:
    """Sign ``message`` using the provided private key hex string.

    The private key is assumed to be a 32‑byte big-endian scalar encoded as
    hex, exactly as returned by :func:`seed_to_keypair`.
    The returned signature is the raw 64‑byte ECDSA value encoded as hex.
    """
    priv = bytes.fromhex(priv_hex)
    sk = SigningKey.from_string(priv, curve=SECP256k1)
    sig = sk.sign(message)
    return sig.hex()


def verify_signature(pub_hex: str, message: bytes, signature_hex: str) -> bool:
    """Verify hex-encoded signature against a message and public key.

    ``pub_hex`` must be a compressed secp256k1 point (as returned by
    :func:`seed_to_keypair`).  The signature is the hex produced by
    :func:`sign_message`.  Returns ``True`` if the signature is valid,
    ``False`` otherwise.
    """
    vk = VerifyingKey.from_string(bytes.fromhex(pub_hex), curve=SECP256k1)
    try:
        return vk.verify(bytes.fromhex(signature_hex), message)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# simple ECIES-style encrypt/decrypt using secp256k1 keys + AES-GCM
# ---------------------------------------------------------------------------

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os


def encrypt_with_public(pub_hex: str, plaintext: bytes) -> bytes:
    """Encrypt ``plaintext`` for the holder of the given public key.

    The recipient public key must be a compressed secp256k1 point encoded as
    hex (same format returned by :func:`seed_to_keypair`).  The returned
    ciphertext is structured as::

        ephemeral_pub(33) || nonce(12) || aes_gcm_ciphertext

    where ``ephemeral_pub`` is a compressed public point generated for each
    encryption.  This is a minimal ECIES-style construction suitable for
    examples; real-world code should use a well-reviewed library.
    """
    recipient_public = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256K1(), bytes.fromhex(pub_hex)
    )

    # ephemeral key for one-time ECDH
    ephemeral_priv = ec.generate_private_key(ec.SECP256K1())
    shared = ephemeral_priv.exchange(ec.ECDH(), recipient_public)

    # derive a symmetric key
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"ecies",
    ).derive(shared)

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext, None)

    eph_pub = ephemeral_priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.CompressedPoint,
    )
    return eph_pub + nonce + ct


def decrypt_with_private(priv_hex: str, ciphertext: bytes) -> bytes:
    """Reverse :func:`encrypt_with_public` using the private key in hex.

    ``ciphertext`` should have the format described above.  The private key
    is interpreted as a big-endian 32‑byte scalar.
    """
    priv_int = int(priv_hex, 16)
    private_key = ec.derive_private_key(priv_int, ec.SECP256K1())

    eph_pub = ciphertext[:33]
    nonce = ciphertext[33:45]
    ct = ciphertext[45:]

    ephemeral_public = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256K1(), eph_pub
    )
    shared = private_key.exchange(ec.ECDH(), ephemeral_public)
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"ecies",
    ).derive(shared)

    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)


if __name__ == "__main__":
    phrase = generate_mnemonic()
    print("24-word seed phrase:\n", phrase)
    seed = mnemonic_to_seed(phrase)
    print("\nseed (hex):", seed.hex())
    priv_hex, pub_hex = seed_to_keypair(seed)
    print("\nprivate key (hex):", priv_hex)
    print("public key (compressed hex):", pub_hex)

    # small demonstration of encryption/decryption
    msg = b"hello world"
    print("\noriginal message:", msg)
    cipher = encrypt_with_public(pub_hex, msg)
    print("ciphertext (hex):", cipher.hex())
    recovered = decrypt_with_private(priv_hex, cipher)
    print("recovered plaintext:", recovered)

    # -----------------------------------------------------------
    # signature demonstration
    # -----------------------------------------------------------
    sig = sign_message(priv_hex, msg)
    print("\nsignature (hex):", sig)
    valid = verify_signature(pub_hex, msg, sig)
    print("signature valid?", valid)
