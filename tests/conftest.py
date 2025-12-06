"""
Shared pytest fixtures for MeetLens backend tests.
Provides test clients and sample data.
Uses real OpenAI API calls.
"""
import pytest
import base64
import uuid
from fastapi.testclient import TestClient
from httpx import AsyncClient
from main import app
from models.messages import SummaryBlock


# Sample test data
SAMPLE_SESSION_ID = str(uuid.uuid4())
SAMPLE_AUDIO_BYTES = b"\x00" * 32000  # 2 seconds of silence at 16kHz mono 16-bit
SAMPLE_AUDIO_BASE64 = base64.b64encode(SAMPLE_AUDIO_BYTES).decode('utf-8')


@pytest.fixture
def sample_session_id():
    """Generate a unique session ID for each test."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_audio_base64():
    """Sample base64-encoded audio data."""
    return SAMPLE_AUDIO_BASE64


@pytest.fixture
def sample_audio_bytes():
    """Sample raw audio bytes."""
    return SAMPLE_AUDIO_BYTES


@pytest.fixture
def mock_whisper_transcript():
    """Mock Whisper transcription response."""
    return "Hello world. This is a test."


@pytest.fixture
def mock_translation():
    """Mock translation response."""
    return "Merhaba dünya. Bu bir test."


@pytest.fixture
def mock_summary_block():
    """Mock summary block response."""
    return SummaryBlock(
        short_overview="This was a test meeting about testing.",
        action_items=["Complete test suite", "Review test results"],
        decisions=["Use pytest for testing", "Mock external APIs"]
    )


@pytest.fixture
def app_instance():
    """FastAPI application instance."""
    return app


@pytest.fixture
def client(app_instance):
    """HTTP test client."""
    return TestClient(app_instance)


@pytest.fixture
async def async_client(app_instance):
    """Async HTTP test client."""
    async with AsyncClient(app=app_instance, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def websocket_client(app_instance):
    """WebSocket test client."""
    return TestClient(app_instance)


@pytest.fixture
def mock_transcribe_audio():
    """Mock for whisper_service.transcribe_audio."""
    async def _mock_transcribe(audio_bytes, audio_format):
        return "Hello world. This is a test."
    return _mock_transcribe


@pytest.fixture
def mock_translate_segment():
    """Mock for translation_service.translate_segment."""
    async def _mock_translate(text, source_lang=None, target_lang=None):
        return f"Translated: {text}"
    return _mock_translate


@pytest.fixture
def mock_generate_summary(mock_summary_block):
    """Mock for summary_service.generate_summary."""
    async def _mock_summary(full_transcript, language=None):
        return mock_summary_block
    return _mock_summary


# Note: Tests use real OpenAI API calls. Make sure OPENAI_API_KEY is set in environment.

