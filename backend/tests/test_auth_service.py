from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.services.auth import (
    InvalidAccessToken,
    create_access_token,
    hash_password,
    verify_access_token,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    encoded = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_access_token_round_trip_and_expiry() -> None:
    user_id = uuid4()
    issued_at = datetime(2026, 9, 22, tzinfo=UTC)
    token = create_access_token(user_id, now=issued_at)

    assert verify_access_token(token, now=issued_at + timedelta(minutes=5)) == user_id
    with pytest.raises(InvalidAccessToken):
        verify_access_token(token, now=issued_at + timedelta(days=8))
