import time

import jwt as pyjwt

from app.config import settings
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

ALGORITHM = "HS256"


def _make_token(department: str, level: int, sub: str = "test-user") -> str:
    """Mints a token the same way mint_tokens.py does, for use in tests."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": f"{sub}@test.com",
        "department": department,
        "level": level,
        "iat": now,
        "exp": now + 3600,
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def test_auth_success_with_valid_token():
    """A valid token should get an auth_success reply with matching claims."""
    token = _make_token("hr", 1, sub="emp-001")
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"type": "auth", "token": token})
        response = ws.receive_json()
        assert response["type"] == "auth_success"
        assert response["user_id"] == "emp-001"
        assert response["department"] == "hr"
        assert response["level"] == 1


def test_auth_failed_with_invalid_token():
    """An invalid token should get auth_failed and the connection should close."""
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"type": "auth", "token": "not-a-real-token"})
        response = ws.receive_json()
        assert response["type"] == "auth_failed"
        assert "message" in response


def test_auth_failed_with_malformed_first_message():
    """The first message must match the auth schema, or auth_failed is sent."""
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"type": "message", "text": "hello"})  # wrong type first
        response = ws.receive_json()
        assert response["type"] == "auth_failed"


def test_message_after_auth_streams_and_completes():
    """After auth, a chat message should yield stream chunks then a done event."""
    token = _make_token("hr", 1, sub="emp-001")
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"type": "auth", "token": token})
        ws.receive_json()  # auth_success

        ws.send_json({"type": "message", "text": "What is the leave policy?"})

        saw_stream = False
        saw_done = False
        for _ in range(500):  # generous cap: streamed answers can be many small token chunks
            response = ws.receive_json()
            if response["type"] == "stream":
                saw_stream = True
            elif response["type"] == "done":
                saw_done = True
                break
            elif response["type"] == "error":
                raise AssertionError(f"server returned an error event: {response['message']}")

        assert saw_stream, "expected at least one stream event"
        assert saw_done, "expected a done event to terminate the response"