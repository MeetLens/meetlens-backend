"""
Translation Service using LiteLLM for multi-provider support.
Translates stable transcript segments from source to target language.
"""
import os
import logging
from typing import Optional
from services.llm_config import TRANSLATION_SERVICE_KEY
from services.llm_service import complete_with_fallback

logger = logging.getLogger(__name__)

# Default languages (can be overridden via environment variables)
DEFAULT_SOURCE_LANG = os.getenv("SOURCE_LANGUAGE", "en")
DEFAULT_TARGET_LANG = os.getenv("TARGET_LANGUAGE", "tr")

async def translate_segment(
    text: str,
    source_lang: str = None,
    target_lang: str = None,
    model: Optional[str] = None,
) -> str:
    """
    Translate a text segment using LiteLLM.

    Args:
        text: Text to translate
        source_lang: Source language code (e.g., "en", "tr")
        target_lang: Target language code (e.g., "tr", "en")
        model: Optional model override; defaults to translation service configuration

    Returns:
        Translated text string

    Raises:
        Exception: If the LLM API returns an unrecoverable error
        Note: RateLimitError and APITimeoutError are handled gracefully with fallback
    """
    if not text or not text.strip():
        return ""

    source_lang = source_lang or DEFAULT_SOURCE_LANG
    target_lang = target_lang or DEFAULT_TARGET_LANG

    try:
        # Build translation prompt
        prompt = (
            f"Translate the following sentence from {source_lang} to {target_lang}. "
            f"Return only the translation, no explanations:\n\n{text}"
        )

        # Call LiteLLM with fallback to source text on rate limit or timeout
        translated_text = await complete_with_fallback(
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional translator. Translate accurately and naturally.",
                },
                {"role": "user", "content": prompt},
            ],
            model=model,
            max_tokens=500,
            request_name="translation",
            fallback_text=text,  # Return source text on rate limit or timeout
            service_key=TRANSLATION_SERVICE_KEY,
        )

        return translated_text

    except Exception as e:
        logger.error(f"Translation failed: {str(e)}")
        raise

