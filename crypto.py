import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_PROJECT_SEED = b"yggtzn:torrent-cache:v1"
_SALT = b"yggtzn-cache-encryption-salt-2024"

def _derive_key() -> bytes:
    return hashlib.pbkdf2_hmac("sha256", _PROJECT_SEED, _SALT, 600_000)

_KEY = _derive_key()
_AESGCM = AESGCM(_KEY)

def encrypt(data: bytes) -> bytes:
    nonce = os.urandom(12)
    ciphertext = _AESGCM.encrypt(nonce, data, None)
    return nonce + ciphertext

def decrypt(data: bytes) -> bytes:
    nonce, ciphertext = data[:12], data[12:]
    return _AESGCM.decrypt(nonce, ciphertext, None)
