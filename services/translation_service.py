"""
Translation Service using OpenAI GPT API.
Translates stable transcript segments from source to target language.
"""
import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# Lazy initialization of OpenAI client
_client = None


def _get_client() -> OpenAI:
    """Get or create OpenAI client instance."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        _client = OpenAI(api_key=api_key)
    return _client

# Default languages (can be overridden via environment variables)
DEFAULT_SOURCE_LANG = os.getenv("SOURCE_LANGUAGE", "en")
DEFAULT_TARGET_LANG = os.getenv("TARGET_LANGUAGE", "tr")


async def translate_segment(
    text: str,
    source_lang: str = None,
    target_lang: str = None
) -> str:
    """
    Translate a text segment using GPT API.
    
    Args:
        text: Text to translate
        source_lang: Source language code (e.g., "en", "tr")
        target_lang: Target language code (e.g., "tr", "en")
    
    Returns:
        Translated text string
    
    Raises:
        Exception: If translation fails
    """
    import asyncio
    
    if not text or not text.strip():
        return ""
    
    source_lang = source_lang or DEFAULT_SOURCE_LANG
    target_lang = target_lang or DEFAULT_TARGET_LANG
    
    try:
        # Build translation prompt
        prompt = f"Translate the following sentence from {source_lang} to {target_lang}. Return only the translation, no explanations:\n\n{text}"
        
        # Call GPT API (run sync call in executor to avoid blocking)
        client = _get_client()
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional translator. Translate accurately and naturally."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
        )
        
        translated_text = response.choices[0].message.content.strip()
        return translated_text
    
    except Exception as e:
        logger.error(f"Translation failed: {str(e)}")
        raise

