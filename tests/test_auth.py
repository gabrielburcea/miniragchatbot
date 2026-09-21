import time

import jwt as pyjwt
import pytest

from app.auth.jwt_tokens import InvalidTokenError, verify_token
from app.config import settings

ALGORITHM = "HS256"


def _make_token(overrides=None, secret=None):
    """Builds a JWT with sane defaults, allowing overrides for edge cases."""
    now = int(time.time())
    payload = {
        "sub": "emp-001",
        "email": "emp@test.com",
        "department": "hr",
        "level": 1,
        "iat": now,
        "exp": now + 3600,
    }
    if overrides:
        payload.update(overrides)
    return pyjwt.encode(payload, secret or settings.jwt_secret, algorithm=ALGORITHM)


def test_valid_token_decodes_successfully():
    """A well-formed, unexpired token returns its claims."""
    token = _make_token()
    claims = verify_token(token)
    assert claims["sub"] == "emp-001"
    assert claims["department"] == "hr"
    assert claims["level"] == 1


def test_expired_token_raises():
    """A token past its exp claim must be rejected."""
    token = _make_token({"iat": int(time.time()) - 7200, "exp": int(time.time()) - 3600})
    with pytest.raises(InvalidTokenError):
        verify_token(token)


def test_tampered_signature_raises():
    """A token signed with the wrong secret must be rejected."""
    token = _make_token(secret="wrong-secret")
    with pytest.raises(InvalidTokenError):
        verify_token(token)


def test_missing_required_claim_raises():
    """A token missing department/level must be rejected."""
    now = int(time.time())
    payload = {"sub": "emp-001", "iat": now, "exp": now + 3600}  # no department/level
    token = pyjwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    with pytest.raises(InvalidTokenError):
        verify_token(token)


def test_garbage_string_raises():
    """A completely malformed token string must be rejected, not crash."""
    with pytest.raises(InvalidTokenError):
        verify_token("not-a-real-jwt")