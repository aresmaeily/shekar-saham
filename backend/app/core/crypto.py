"""
app/core/crypto.py - v0.6.1 Fix: Singleton Fernet
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from functools import lru_cache
from typing import Optional

logger = logging.getLogger("shekar.crypto")

try:
    from cryptography.fernet import Fernet, InvalidToken
    HAS_CRYPTO = True
except ImportError:
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore
    HAS_CRYPTO = False


def _derive_key_from_secret(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def get_fernet() -> Optional[Fernet]:
    if not HAS_CRYPTO:
        logger.warning("cryptography not installed")
        return None
    
    fernet_key = os.getenv("FERNET_KEY", "").strip()
    if fernet_key:
        try:
            if len(fernet_key) == 44:
                return Fernet(fernet_key.encode())
            return Fernet(_derive_key_from_secret(fernet_key))
        except Exception as exc:
            logger.warning(f"Invalid FERNET_KEY: {exc}")
    
    api_key = os.getenv("API_KEY", "").strip()
    if api_key:
        return Fernet(_derive_key_from_secret(api_key))
    
    # Singleton ephemeral key - cache ensures same key per process
    logger.warning("No FERNET_KEY/API_KEY - using ephemeral singleton key")
    ephemeral = Fernet.generate_key()
    return Fernet(ephemeral)


def encrypt_token(plain: str) -> str:
    if not plain:
        return ""
    f = get_fernet()
    if not f:
        return base64.b64encode(f"plain:{plain}".encode()).decode()
    try:
        return f.encrypt(plain.encode()).decode()
    except Exception as exc:
        logger.error(f"encrypt failed: {exc}")
        return ""


def decrypt_token(cipher: str) -> str:
    if not cipher:
        return ""
    f = get_fernet()
    if f:
        try:
            return f.decrypt(cipher.encode()).decode()
        except InvalidToken:
            pass
        except Exception:
            pass
    try:
        decoded = base64.b64decode(cipher.encode()).decode()
        if decoded.startswith("plain:"):
            return decoded[6:]
        return decoded
    except Exception:
        pass
    # heuristic for old plain tokens
    if len(cipher) > 10 and not cipher.startswith("gAAAA"):
        # If it looks like plain token, return
        if "bot" in cipher.lower() or ":" in cipher or len(cipher) > 30:
            return cipher
    return ""


def is_encrypted(value: str) -> bool:
    if not value:
        return False
    return value.startswith("gAAAAA")
