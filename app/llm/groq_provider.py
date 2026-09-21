"""
Groq implementation of the LLMProvider interface.

Tool calls and streaming don't mix cleanly in the Groq/OpenAI-style API, so
this uses the standard two-phase pattern: a non-streamed call first to let
the model decide whether it needs a tool, then a streamed call for the
final natural-language answer once no more tools are needed.
"""

import json

from groq import AsyncGroq

from app.config import settings
from app.llm.base import LLMProvider

_MAX_TOOL_ROUNDS = 3  # safety cap against infinite tool-call loops


class GroqProvider(LLMProvider):
    def __init__(self):
        self._client = AsyncGroq(api_key=settings.groq_api_key)
        self._model = settings.groq_model

    async def stream_chat(self, messages, tools=None, tool_executor=None):
        """
        Yields {"type": "text", "text": "..."} chunks, and optionally
        {"type": "tool_call", "name": ..., "arguments": ...} for visibility.

        tool_executor: async callable(name, arguments_dict) -> result dict,
        used to actually run a requested tool before continuing.
        """
        working_messages = list(messages)

        for _ in range(_MAX_TOOL_ROUNDS):
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=working_messages,
                tools=tools,
            )
            message = response.choices[0].message

            if not message.tool_calls:
                # No tool needed -- this path shouldn't normally hit since we
                # stream the final answer separately, but guards empty tool list
                working_messages.append({"role": "assistant", "content": message.content or ""})
                break

            # Model wants to call one or more tools
            working_messages.append({
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ],
            })

            for tc in message.tool_calls:
                args = json.loads(tc.function.arguments)
                yield {"type": "tool_call", "name": tc.function.name, "arguments": args}
                result = await tool_executor(tc.function.name, args)
                working_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": json.dumps(result),
                })
        else:
            raise RuntimeError("exceeded max tool-call rounds")

        # Final streamed answer, now that no more tools are being requested
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=working_messages,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield {"type": "text", "text": delta}