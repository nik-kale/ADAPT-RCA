"""
Base LLM provider interface.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class LLMMessage(BaseModel):
    """A message in an LLM conversation."""
    role: str  # "system", "user", or "assistant"
    content: str


class LLMResponse(BaseModel):
    """Response from an LLM."""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All LLM providers (OpenAI, Anthropic, local models, etc.)
    should implement this interface.
    """

    def __init__(self, model: str, api_key: Optional[str] = None, **kwargs: Any):
        """
        Initialize the LLM provider.

        Args:
            model: Model identifier (e.g., "gpt-4", "claude-3-opus")
            api_key: API key for the provider
            **kwargs: Additional provider-specific parameters
        """
        self.model = model
        self.api_key = api_key
        self.kwargs = kwargs

    @abstractmethod
    def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Generate a completion from the LLM.

        Args:
            messages: List of conversation messages
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse containing the completion

        Raises:
            Exception: If the API call fails
        """
        pass

    def create_system_message(self, content: str) -> LLMMessage:
        """Create a system message."""
        return LLMMessage(role="system", content=content)

    def create_user_message(self, content: str) -> LLMMessage:
        """Create a user message."""
        return LLMMessage(role="user", content=content)

    def create_assistant_message(self, content: str) -> LLMMessage:
        """Create an assistant message."""
        return LLMMessage(role="assistant", content=content)
