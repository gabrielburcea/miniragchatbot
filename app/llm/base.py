"""
Abstract interface every LLM provider must implement.

The rest of the app (WebSocket handler) only depends on this interface,
never on a concrete provider like Groq directly. This is what makes the
provider swappable per README requirement 6 -- a new provider just needs
to implement stream_chat() with the same signature.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

# Executes a single tool call: (tool_name, arguments_dict) -> result_dict
ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class LLMProvider(ABC):
    """Base class for a streaming, tool-calling capable chat provider."""

    @abstractmethod
    def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Streams the model's response as a sequence of events.

        Each yielded event is one of:
          {"type": "text", "text": "..."}
            - a chunk of the final streamed answer

          {"type": "tool_call", "name": "...", "arguments": {...}}
            - the model is invoking a tool; tool_executor is called
              internally to produce the result before continuing

        tool_executor is required if `tools` is non-empty -- it is the
        function that actually runs the requested tool (e.g. calling
        get_employee_context) and returns its result as a dict.
        """
        raise NotImplementedError