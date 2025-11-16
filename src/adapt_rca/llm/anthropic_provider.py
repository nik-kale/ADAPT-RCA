"""
Anthropic LLM provider.
"""
import logging
from typing import List, Optional

from .base import LLMProvider, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic API provider for Claude models."""

    def __init__(
        self,
        model: str = "claude-3-sonnet-20240229",
        api_key: Optional[str] = None,
        **kwargs
    ):
        super().__init__(model, api_key, **kwargs)

        try:
            import anthropic
            self.anthropic = anthropic
        except ImportError:
            raise ImportError(
                "Anthropic package not installed. Install with: pip install anthropic"
            )

        if api_key:
            self.client = anthropic.Anthropic(api_key=api_key)
        else:
            # Will use ANTHROPIC_API_KEY environment variable
            self.client = anthropic.Anthropic()

    def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Generate a completion using Anthropic API.

        Args:
            messages: List of conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with the completion
        """
        # Anthropic requires system message separate
        system_message = None
        conversation_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                conversation_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        logger.debug(f"Calling Anthropic API with model {self.model}")

        try:
            kwargs = {
                "model": self.model,
                "messages": conversation_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 1024
            }

            if system_message:
                kwargs["system"] = system_message

            response = self.client.messages.create(**kwargs)

            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                },
                finish_reason=response.stop_reason
            )
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise
