"""
Anthropic LLM provider.
"""
import logging
from typing import List, Optional
import time

from .base import LLMProvider, LLMMessage, LLMResponse
from ..constants import DEFAULT_ANTHROPIC_MODEL, DEFAULT_LLM_TIMEOUT_SECONDS
from ..security import sanitize_api_error, sanitize_for_llm
from ..exceptions import LLMError, LLMTimeoutError, LLMRateLimitError

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic API provider for Claude models."""

    def __init__(
        self,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        api_key: Optional[str] = None,
        timeout: int = DEFAULT_LLM_TIMEOUT_SECONDS,
        **kwargs
    ):
        super().__init__(model, api_key, **kwargs)
        self.timeout = timeout

        try:
            import anthropic
            self.anthropic = anthropic
        except ImportError:
            raise ImportError(
                "Anthropic package not installed. Install with: pip install anthropic"
            )

        if api_key:
            self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        else:
            # Will use ANTHROPIC_API_KEY environment variable
            self.client = anthropic.Anthropic(timeout=timeout)

    def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        max_retries: int = 3
    ) -> LLMResponse:
        """
        Generate a completion using Anthropic API with retry logic.

        Args:
            messages: List of conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            max_retries: Maximum number of retry attempts

        Returns:
            LLMResponse with the completion

        Raises:
            LLMError: For general LLM errors
            LLMTimeoutError: When API call times out
            LLMRateLimitError: When rate limit is exceeded
        """
        # Anthropic requires system message separate
        system_message = None
        conversation_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                # Sanitize user content to prevent prompt injection
                if msg.role == "user":
                    content = sanitize_for_llm(msg.content, max_length=4000)
                else:
                    content = msg.content
                conversation_messages.append({
                    "role": msg.role,
                    "content": content
                })

        logger.debug(f"Calling Anthropic API with model {self.model} (timeout: {self.timeout}s)")

        # Exponential backoff retry logic
        for attempt in range(max_retries):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": conversation_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens or 1024,
                    "timeout": self.timeout
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

            except self.anthropic.APITimeoutError as e:
                sanitized_error = sanitize_api_error(e)
                logger.error(f"Anthropic API timeout: {sanitized_error}")
                if attempt == max_retries - 1:
                    raise LLMTimeoutError(timeout=self.timeout, provider="Anthropic") from e
                # Exponential backoff
                wait_time = 2 ** attempt
                logger.info(f"Retrying after {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)

            except self.anthropic.RateLimitError as e:
                sanitized_error = sanitize_api_error(e)
                logger.error(f"Anthropic API rate limit: {sanitized_error}")
                if attempt == max_retries - 1:
                    raise LLMRateLimitError() from e
                # Longer wait for rate limits
                wait_time = 5 * (2 ** attempt)
                logger.info(f"Rate limited, retrying after {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)

            except Exception as e:
                sanitized_error = sanitize_api_error(e)
                logger.error(f"Anthropic API error: {sanitized_error}")
                if attempt == max_retries - 1:
                    raise LLMError(f"Anthropic API failed after {max_retries} attempts: {sanitized_error}") from e
                # Exponential backoff for other errors
                wait_time = 2 ** attempt
                logger.info(f"Error occurred, retrying after {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
