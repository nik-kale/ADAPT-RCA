"""
OpenAI LLM provider.
"""
import logging
from typing import List, Optional

from .base import LLMProvider, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI API provider for GPT models."""

    def __init__(self, model: str = "gpt-4", api_key: Optional[str] = None, **kwargs):
        super().__init__(model, api_key, **kwargs)

        try:
            import openai
            self.openai = openai
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Install with: pip install openai"
            )

        if api_key:
            self.client = openai.OpenAI(api_key=api_key)
        else:
            # Will use OPENAI_API_KEY environment variable
            self.client = openai.OpenAI()

    def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Generate a completion using OpenAI API.

        Args:
            messages: List of conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with the completion
        """
        # Convert to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        logger.debug(f"Calling OpenAI API with model {self.model}")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                finish_reason=response.choices[0].finish_reason
            )
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
