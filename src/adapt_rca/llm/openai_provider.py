"""
OpenAI LLM provider.
"""
import logging
from typing import List, Optional
import time

from .base import LLMProvider, LLMMessage, LLMResponse
from ..constants import DEFAULT_OPENAI_MODEL, DEFAULT_LLM_TIMEOUT_SECONDS
from ..security import sanitize_api_error, sanitize_for_llm
from ..exceptions import LLMError, LLMTimeoutError, LLMRateLimitError

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI API provider for GPT models."""

    def __init__(
        self,
        model: str = DEFAULT_OPENAI_MODEL,
        api_key: Optional[str] = None,
        timeout: int = DEFAULT_LLM_TIMEOUT_SECONDS,
        **kwargs
    ):
        super().__init__(model, api_key, **kwargs)
        self.timeout = timeout

        try:
            import openai
            self.openai = openai
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Install with: pip install openai"
            )

        if api_key:
            self.client = openai.OpenAI(api_key=api_key, timeout=timeout)
        else:
            # Will use OPENAI_API_KEY environment variable
            self.client = openai.OpenAI(timeout=timeout)

    def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        max_retries: int = 3
    ) -> LLMResponse:
        """
        Generate a completion using OpenAI API with retry logic.

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
        # Sanitize user content to prevent prompt injection
        sanitized_messages = []
        for msg in messages:
            # Only sanitize user messages, not system/assistant
            if msg.role == "user":
                content = sanitize_for_llm(msg.content, max_length=4000)
                sanitized_messages.append({"role": msg.role, "content": content})
            else:
                sanitized_messages.append({"role": msg.role, "content": msg.content})

        logger.debug(f"Calling OpenAI API with model {self.model} (timeout: {self.timeout}s)")

        # Exponential backoff retry logic
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=sanitized_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=self.timeout
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

            except self.openai.Timeout as e:
                sanitized_error = sanitize_api_error(e)
                logger.error(f"OpenAI API timeout: {sanitized_error}")
                if attempt == max_retries - 1:
                    raise LLMTimeoutError(timeout=self.timeout, provider="OpenAI") from e
                # Exponential backoff: 2^attempt seconds
                wait_time = 2 ** attempt
                logger.info(f"Retrying after {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)

            except self.openai.RateLimitError as e:
                sanitized_error = sanitize_api_error(e)
                logger.error(f"OpenAI API rate limit: {sanitized_error}")
                if attempt == max_retries - 1:
                    raise LLMRateLimitError() from e
                # Longer wait for rate limits
                wait_time = 5 * (2 ** attempt)
                logger.info(f"Rate limited, retrying after {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)

            except Exception as e:
                sanitized_error = sanitize_api_error(e)
                logger.error(f"OpenAI API error: {sanitized_error}")
                if attempt == max_retries - 1:
                    raise LLMError(f"OpenAI API failed after {max_retries} attempts: {sanitized_error}") from e
                # Exponential backoff for other errors
                wait_time = 2 ** attempt
                logger.info(f"Error occurred, retrying after {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
