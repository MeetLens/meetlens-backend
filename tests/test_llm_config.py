import importlib
import json
import pytest

from services import llm_config


@pytest.fixture(autouse=True)
def reload_llm_config():
    # Ensure a clean module state for each test
    importlib.reload(llm_config)


def test_llm_config_env_overrides(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-3-sonnet")
    monkeypatch.setenv("SUMMARY_PROVIDER", "openai")
    monkeypatch.setenv("SUMMARY_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("TRANSLATION_PROVIDER", "google")
    monkeypatch.setenv("TRANSLATION_MODEL", "gemini/gemini-1.5-flash")

    importlib.reload(llm_config)

    default_cfg = llm_config.get_llm_config()
    summary_cfg = llm_config.get_llm_config(llm_config.SUMMARY_SERVICE_KEY)
    translation_cfg = llm_config.get_llm_config(llm_config.TRANSLATION_SERVICE_KEY)

    assert default_cfg.provider == "anthropic"
    assert default_cfg.model == "claude-3-sonnet"
    assert summary_cfg.provider == "openai"
    assert summary_cfg.model == "gpt-4o-mini"
    assert translation_cfg.provider == "google"
    assert translation_cfg.model == "gemini/gemini-1.5-flash"


def test_get_llm_config_model_override_retains_connection_settings(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "secret-token")
    importlib.reload(llm_config)

    base = llm_config.get_llm_config(llm_config.NEBIUS_SERVICE_KEY)
    override = llm_config.get_llm_config(
        llm_config.NEBIUS_SERVICE_KEY, model_override="custom-nebius-model"
    )

    assert base.base_url == llm_config.NEBIUS_BASE_URL
    assert override.base_url == llm_config.NEBIUS_BASE_URL
    assert override.api_key == base.api_key == "secret-token"
    assert override.provider == base.provider == "nebius"
    assert override.model == "custom-nebius-model"


@pytest.mark.asyncio
async def test_nebius_completion_uses_configured_base_url(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "secret-token")
    importlib.reload(llm_config)
    from services import llm_service  # Import after env setup

    importlib.reload(llm_service)

    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)

        class Message:
            content = "nebius reply"

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]
            usage = None

        return Response()

    monkeypatch.setattr(llm_service, "acompletion", fake_acompletion)
    monkeypatch.setattr(
        llm_service.usage_tracker,
        "track_completion_response",
        lambda *args, **kwargs: None,
    )

    result = await llm_service.complete(
        messages=[{"role": "user", "content": "Hello"}],
        service_key=llm_config.NEBIUS_SERVICE_KEY,
    )

    assert result == "nebius reply"
    assert captured["model"] == llm_config.NEBIUS_MODEL
    assert captured["api_base"] == llm_config.NEBIUS_BASE_URL
    assert captured["api_key"] == "secret-token"


@pytest.mark.asyncio
async def test_openai_completion_uses_default_route(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1-mini")
    importlib.reload(llm_config)
    from services import llm_service

    importlib.reload(llm_service)

    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)

        class Message:
            content = "openai reply"

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]
            usage = None

        return Response()

    monkeypatch.setattr(llm_service, "acompletion", fake_acompletion)
    monkeypatch.setattr(
        llm_service.usage_tracker,
        "track_completion_response",
        lambda *args, **kwargs: None,
    )

    result = await llm_service.complete(
        messages=[{"role": "user", "content": "Hello"}],
        service_key=None,
    )

    assert result == "openai reply"
    assert captured["model"] == "gpt-4.1-mini"
    assert "api_base" not in captured
    assert "api_key" not in captured


@pytest.mark.asyncio
async def test_translation_delegates_to_translation_service(monkeypatch):
    from services import translation_service

    recorded = {}

    async def fake_complete_with_fallback(**kwargs):
        recorded.update(kwargs)
        return "translated"

    monkeypatch.setattr(
        translation_service, "complete_with_fallback", fake_complete_with_fallback
    )

    result = await translation_service.translate_segment(
        "Hello there", source_lang="en", target_lang="es"
    )

    assert result == "translated"
    assert recorded["service_key"] == translation_service.TRANSLATION_SERVICE_KEY
    assert recorded["request_name"] == "translation"
    assert recorded["fallback_text"] == "Hello there"


@pytest.mark.asyncio
async def test_summary_delegates_to_summary_service(monkeypatch):
    from services import summary_service

    recorded = {}

    async def fake_complete_with_fallback(**kwargs):
        recorded.update(kwargs)
        return json.dumps({
            "short_overview": "Overview", "action_items": [], "decisions": []
        })

    monkeypatch.setattr(
        summary_service, "complete_with_fallback", fake_complete_with_fallback
    )

    summary = await summary_service.generate_summary("Meeting transcript", language="en")

    assert summary.short_overview == "Overview"
    assert recorded["service_key"] == summary_service.SUMMARY_SERVICE_KEY
    assert recorded["request_name"] == "summary"
    assert recorded["response_format"] == {"type": "json_object"}
