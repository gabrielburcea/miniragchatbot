"""
The /ws/chat WebSocket endpoint: auth, then RBAC-filtered RAG chat.

Protocol (see README):
  1. Client sends {"type": "auth", "token": "..."}
  2. Server replies auth_success or auth_failed (closes on failure)
  3. Client sends {"type": "message", "text": "..."}
  4. Server streams {"type": "stream", "text": "..."} chunks, then {"type": "done"}
  5. Any LLM/tool failure sends {"type": "error", ...} but keeps the connection open
"""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.auth.jwt_tokens import InvalidTokenError, verify_token
from app.llm.factory import get_llm_provider
from app.llm.tools import get_employee_context
from app.models.schemas import (
    AuthFailedResponse,
    AuthMessage,
    AuthSuccessResponse,
    ChatMessage,
    DoneResponse,
    ErrorResponse,
    StreamResponse,
)
from app.rag.retriever import retrieve_chunks
from app.llm.prompts import build_system_prompt

router = APIRouter()

# The one tool the LLM is allowed to call, per README requirement 5
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_employee_context",
            "description": "Fetch the current user's profile, manager, and team info",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The employee's user id"},
                },
                "required": ["user_id"],
            },
        },
    }
]


async def _tool_executor(name: str, arguments: dict) -> dict:
    """Routes a tool call by name to its implementation."""
    if name == "get_employee_context":
        return await get_employee_context(arguments["user_id"])
    raise ValueError(f"unknown tool: {name}")


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    await websocket.accept()

    # --- Step 1: auth ---
    try:
        first_raw = await websocket.receive_text()
        auth_msg = AuthMessage.model_validate_json(first_raw)
    except (ValidationError, json.JSONDecodeError):
        await websocket.send_json(AuthFailedResponse(message="first message must be a valid auth message").model_dump())
        await websocket.close()
        return

    try:
        claims = verify_token(auth_msg.token)
    except InvalidTokenError as e:
        await websocket.send_json(AuthFailedResponse(message=str(e)).model_dump())
        await websocket.close()
        return

    user_id = claims["sub"]
    department = claims["department"]
    level = claims["level"]

    await websocket.send_json(
        AuthSuccessResponse(user_id=user_id, department=department, level=level).model_dump()
    )

    provider = get_llm_provider()

    # --- Step 2: message loop ---
    try:
        while True:
            raw = await websocket.receive_text()

            try:
                chat_msg = ChatMessage.model_validate_json(raw)
            except (ValidationError, json.JSONDecodeError):
                await websocket.send_json(ErrorResponse(message="expected a message with type='message'").model_dump())
                continue

            try:
                chunks = await asyncio.to_thread(retrieve_chunks, chat_msg.text, department, level, 5)
                messages = [
                    {"role": "system", "content": build_system_prompt(user_id, department, level, chunks)},
                    {"role": "user", "content": chat_msg.text},
                ]

                async for event in provider.stream_chat(messages, tools=TOOLS_SCHEMA, tool_executor=_tool_executor):
                    if event["type"] == "text":
                        await websocket.send_json(StreamResponse(text=event["text"]).model_dump())

                await websocket.send_json(DoneResponse().model_dump())

            except Exception as e:
                # LLM/tool failure: user-facing error, connection stays open
                await websocket.send_json(ErrorResponse(message=f"failed to generate a response: {e}").model_dump())

    except WebSocketDisconnect:
        pass