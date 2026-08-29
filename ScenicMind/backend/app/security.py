from __future__ import annotations

import hashlib
import hmac
import secrets


PBKDF2_ITERATIONS = 240_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        iterations_text, salt_hex, digest_hex = encoded.split("$", 2)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations_text)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


def create_token() -> str:
    return secrets.token_urlsafe(36)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

