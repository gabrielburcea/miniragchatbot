"""
Factory that returns the configured LLM provider.

This is the single place that decides which concrete LLMProvider to
instantiate. Swapping providers (e.g. for a different employer's key)
only requires changing this function, not any calling code.
"""

from app.llm.base import LLMProvider
from app.llm.groq_provider import GroqProvider


def get_llm_provider() -> LLMProvider:
    """Returns the active LLM provider. Currently hardcoded to Groq."""
    return GroqProvider()