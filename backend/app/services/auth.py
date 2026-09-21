"""Small, dependency-free password and access-token helpers for visitor auth."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.config import settings

PASSWORD_ITERATIONS = 310_000
ACCESS_TOKEN_TTL = timedelta(days=7)


class InvalidAccessToken(ValueError):
    """Raised when a visitor token is missing, expired, or tampered with."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iteration_text, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iteration_text)
        expected = _decode(digest_text)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), _decode(salt_text), iterations
        )
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError, binascii.Error):
        return False


def create_access_token(user_id: UUID, *, now: datetime | None = None) -> str:
    issued_at = now or datetime.now(UTC)
    expires_at = int((issued_at + ACCESS_TOKEN_TTL).timestamp())
    payload = f"{user_id}:{expires_at}".encode()
    signature = hmac.new(settings.auth_secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return f"{_encode(payload)}.{_encode(signature)}"


def verify_access_token(token: str, *, now: datetime | None = None) -> UUID:
    try:
        payload_text, signature_text = token.split(".", 1)
        payload = _decode(payload_text)
        signature = _decode(signature_text)
        expected = hmac.new(
            settings.auth_secret.encode("utf-8"), payload, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected):
            raise InvalidAccessToken
        user_text, expires_text = payload.decode("utf-8").split(":", 1)
        expires_at = int(expires_text)
        current_time = now or datetime.now(UTC)
        if expires_at <= int(current_time.timestamp()):
            raise InvalidAccessToken
        return UUID(user_text)
    except (TypeError, ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise InvalidAccessToken from error


def normalize_email(email: str) -> str:
    return email.strip().lower()


def valid_email(email: str) -> bool:
    local, separator, domain = email.rpartition("@")
    return bool(separator and local and domain and "." in domain and " " not in email)
