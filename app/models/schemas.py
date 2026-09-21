"""Pydantic models for the /ws/chat WebSocket protocol messages."""

from typing import Literal

from pydantic import BaseModel


class AuthMessage(BaseModel):
    """First message a client must send: the JWT to authenticate with."""

    type: Literal["auth"]
    token: str


class ChatMessage(BaseModel):
    """A user's chat message, sent after successful auth."""

    type: Literal["message"]
    text: str


class AuthSuccessResponse(BaseModel):
    type: Literal["auth_success"] = "auth_success"
    user_id: str
    department: str
    level: int


class AuthFailedResponse(BaseModel):
    type: Literal["auth_failed"] = "auth_failed"
    message: str


class StreamResponse(BaseModel):
    type: Literal["stream"] = "stream"
    text: str


class DoneResponse(BaseModel):
    type: Literal["done"] = "done"


class ErrorResponse(BaseModel):
    type: Literal["error"] = "error"
    message: str