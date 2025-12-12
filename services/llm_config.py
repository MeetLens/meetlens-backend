"""Configuration helpers for LLM provider and model selection."""
import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class LLMServiceConfig:
    provider: str
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None


DEFAULT_SERVICE_KEY = "default"
SUMMARY_SERVICE_KEY = "summary"
TRANSLATION_SERVICE_KEY = "translation"
NEBIUS_SERVICE_KEY = "nebius"

# Shared defaults
DEFAULT_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-mini")

# Provider-specific configs
NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
NEBIUS_MODEL = "openai/gpt-oss-120b"
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")

LLM_SERVICE_CONFIGS: Dict[str, LLMServiceConfig] = {
    DEFAULT_SERVICE_KEY: LLMServiceConfig(
        provider=DEFAULT_LLM_PROVIDER,
        model=DEFAULT_LLM_MODEL,
    ),
    SUMMARY_SERVICE_KEY: LLMServiceConfig(
        provider=os.getenv("SUMMARY_PROVIDER", DEFAULT_LLM_PROVIDER),
        model=os.getenv("SUMMARY_MODEL", "gpt-5-nano"),
    ),
    TRANSLATION_SERVICE_KEY: LLMServiceConfig(
        provider=os.getenv("TRANSLATION_PROVIDER", DEFAULT_LLM_PROVIDER),
        model=os.getenv("TRANSLATION_MODEL", "gpt-4.1-mini"),
    ),
    NEBIUS_SERVICE_KEY: LLMServiceConfig(
        provider="nebius",
        model=NEBIUS_MODEL,
        base_url=NEBIUS_BASE_URL,
        api_key=NEBIUS_API_KEY,
    ),
}


def get_llm_config(service_key: Optional[str] = None, model_override: Optional[str] = None) -> LLMServiceConfig:
    """Return the LLM configuration for a given service key.

    Args:
        service_key: Logical service key used to look up provider/model settings.
        model_override: Optional model name override.

    Returns:
        LLMServiceConfig with provider, model, base_url, and api_key set.
    """

    key = service_key or DEFAULT_SERVICE_KEY
    base_config = LLM_SERVICE_CONFIGS.get(key, LLM_SERVICE_CONFIGS[DEFAULT_SERVICE_KEY])

    if model_override is None:
        return base_config

    return LLMServiceConfig(
        provider=base_config.provider,
        model=model_override,
        base_url=base_config.base_url,
        api_key=base_config.api_key,
    )
