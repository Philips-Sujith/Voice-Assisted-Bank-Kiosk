from __future__ import annotations

import base64
import hashlib
import hmac
import os
from pathlib import Path

from Crypto.Hash import HMAC, SHA256


class KeyConfigurationError(RuntimeError):
    pass


DEFAULT_KEY_FILE = Path(__file__).resolve().parent / "data" / "signing_key.bin"


def load_signing_key(key_file: Path | None) -> bytes:
    if key_file is not None and key_file.exists():
        try:
            key = key_file.read_bytes()
        except OSError as exc:
            raise KeyConfigurationError("unable to read signing key file") from exc
    else:
        encoded_key = os.environ.get("SECURITY_SVC_KEY_B64")
        if encoded_key:
            try:
                key = base64.b64decode(encoded_key, validate=True)
            except ValueError as exc:
                raise KeyConfigurationError("SECURITY_SVC_KEY_B64 is not valid Base64") from exc
        else:
            if DEFAULT_KEY_FILE.exists():
                key = DEFAULT_KEY_FILE.read_bytes()
            else:
                DEFAULT_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
                key = os.urandom(32)
                DEFAULT_KEY_FILE.write_bytes(key)

    if len(key) < 32:
        raise KeyConfigurationError("signing key must contain at least 32 bytes")
    return key


def sign_hmac_sha256(key: bytes, message: bytes) -> str:
    signer = HMAC.new(key, digestmod=SHA256)
    signer.update(message)
    return signer.hexdigest()


def verify_hmac_sha256(key: bytes, message: bytes, signature: str) -> bool:
    expected = sign_hmac_sha256(key, message)
    return hmac.compare_digest(expected, signature)
