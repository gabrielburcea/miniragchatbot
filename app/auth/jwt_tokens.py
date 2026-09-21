"""
Verifies JWTs minted by mint_tokens.py and extracts user claims.

The WebSocket /ws/chat endpoint receives a token from the client as the very
first message. This module decodes and validates that token, returning the
claims needed downstream: `sub` (user id), `department`, and `level`. Those
two values feed directly into the RBAC filter built in app/rag/retriever.py.

Tokens are signed with HS256 using JWT_SECRET (shared secret, symmetric
signing) — the same secret used by mint_tokens.py to mint them. No public/
private key pair is needed since both sides trust the same .env value.

Failure modes are collapsed into a single InvalidTokenError so the caller
(the WebSocket handler) only needs to catch one exception type and respond
with {"type": "auth_failed", ...} regardless of *why* the token was rejected.
"""

import jwt

from app.config import settings

ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    """Raised when a token is malformed, expired, or has a bad signature."""


def verify_token(token: str) -> dict:
    """Decodes and validates a JWT, returning its claims as a dict."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("token has expired")
    except jwt.InvalidTokenError:
        raise InvalidTokenError("token is invalid")

    for required_field in ("sub", "department", "level"):
        if required_field not in payload:
            raise InvalidTokenError(f"token missing required claim: {required_field}")

    return payload