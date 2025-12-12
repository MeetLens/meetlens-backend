"""
LLM Service using LiteLLM for multi-provider support.
Provides a unified interface for OpenAI, Claude, Gemini, and other LLM providers.
"""
import logging
from typing import List, Dict, Optional, Any
import litellm
from litellm import acompletion, RateLimitError, Timeout
from services.usage_tracker import usage_tracker
from services.llm_config import get_llm_config

logger = logging.getLogger(__name__)

# Configure LiteLLM
litellm.drop_params = True  # Drop unsupported params instead of raising errors
litellm.suppress_debug_info = True  # Reduce verbose logging


async def complete(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    response_format: Optional[Dict[str, str]] = None,
    request_name: str = "completion",
    service_key: Optional[str] = None,
) -> str:
    """
    Generate a completion using LiteLLM with multi-provider support.

    Args:
        messages: List of message dicts with 'role' and 'content' keys
        model: Model name to use (provider-specific format, e.g., "gpt-4", "claude-3-sonnet")
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (0.0 to 2.0)
        response_format: Response format specification (e.g., {"type": "json_object"})
        request_name: Human-readable name for tracking purposes
        service_key: Logical service key to determine provider/model/base URL/api key

    Returns:
        The text content from the completion response

    Raises:
        RateLimitError: If the API returns a rate limit error (after retries)
        Timeout: If the API request times out
        Exception: For other API errors
    """
    if not messages:
        raise ValueError("Messages list cannot be empty")

    llm_config = get_llm_config(service_key=service_key, model_override=model)

    if not llm_config.model:
        raise ValueError("Model must be specified")

    try:
        # Build completion kwargs
        completion_kwargs: Dict[str, Any] = {
            "model": llm_config.model,
            "messages": messages,
        }

        if max_tokens is not None:
            completion_kwargs["max_tokens"] = max_tokens

        if temperature is not None:
            completion_kwargs["temperature"] = temperature

        if response_format is not None:
            completion_kwargs["response_format"] = response_format

        if llm_config.base_url:
            completion_kwargs["api_base"] = llm_config.base_url

        if llm_config.api_key:
            completion_kwargs["api_key"] = llm_config.api_key

        # Call LiteLLM async completion
        response = await acompletion(**completion_kwargs)

        # Track usage for cost monitoring
        usage_tracker.track_completion_response(
            model=llm_config.model,
            response=response,
            request_name=request_name,
        )

        # Extract and return text content
        content = response.choices[0].message.content
        if content is None:
            logger.warning("Received empty content from %s completion", llm_config.model)
            return ""

        return content.strip()

    except RateLimitError as e:
        logger.warning("LLM completion rate limited for %s: %s", request_name, e)
        raise
    except Timeout as e:
        logger.warning("LLM completion timed out for %s: %s", request_name, e)
        raise
    except Exception as e:
        logger.error("LLM completion failed for %s: %s", request_name, e)
        raise


async def complete_with_fallback(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    response_format: Optional[Dict[str, str]] = None,
    request_name: str = "completion",
    fallback_text: Optional[str] = None,
    service_key: Optional[str] = None,
) -> str:
    """
    Generate a completion with graceful fallback handling.

    This function wraps the complete() function and catches rate limit
    and timeout errors, returning a fallback text instead of raising.

    Args:
        messages: List of message dicts with 'role' and 'content' keys
        model: Model name to use
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        response_format: Response format specification
        request_name: Human-readable name for tracking
        fallback_text: Text to return on rate limit or timeout (None to raise)
        service_key: Logical service key to determine provider/model/base URL/api key

    Returns:
        Completion text or fallback text

    Raises:
        Exception: For non-recoverable errors (not rate limits or timeouts)
    """
    try:
        return await complete(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
            request_name=request_name,
            service_key=service_key,
        )
    except (RateLimitError, Timeout) as e:
        if fallback_text is not None:
            logger.warning(
                "%s fallback triggered due to %s: returning fallback text",
                request_name,
                type(e).__name__,
            )
            return fallback_text
        raise
