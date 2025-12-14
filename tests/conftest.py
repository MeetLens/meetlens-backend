"""
Shared pytest fixtures for MeetLens backend tests.
Provides test clients and sample data.
Uses real OpenAI API calls.
"""
import asyncio
import pytest
import pytest_asyncio
import base64
import uuid
import os
import sqlalchemy as sa
from sqlalchemy import event
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from main import app
from models.messages import SummaryBlock
from database.config import Base
import database.models  # noqa: F401  (register ORM models on Base.metadata)


# pytest-asyncio provides a function-scoped `event_loop` by default.
# Because we have session-scoped async fixtures (e.g. `test_engine`), we need a
# session-scoped event loop to avoid ScopeMismatch errors.
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


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


@pytest_asyncio.fixture
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


# Database fixtures for testing
@pytest.fixture(scope="session")
def test_db_url():
    """Get test database URL from environment or use default."""
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/meetlens_test"
    )


@pytest_asyncio.fixture(scope="session")
async def test_engine(test_db_url):
    """Create test database engine."""
    engine = create_async_engine(test_db_url, echo=False, pool_pre_ping=True)

    # Create all tables
    async with engine.begin() as conn:
        # Required for PostgreSQL-native types/defaults used by our models/migrations
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Create a fresh database session for each test."""
    # We need strong isolation even if code under test calls `session.commit()`.
    # Strategy:
    # - Open a dedicated connection per test
    # - Start an outer transaction on that connection
    # - Use a nested transaction (SAVEPOINT) in the session
    # - Automatically restart the SAVEPOINT after each commit
    async with test_engine.connect() as conn:
        outer_tx = await conn.begin()

        session_factory = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        async with session_factory() as session:
            await session.begin_nested()

            @event.listens_for(session.sync_session, "after_transaction_end")
            def _restart_savepoint(sess, trans):  # type: ignore[no-redef]
                # If the nested transaction ended, re-open it so the test can
                # continue using `commit()` safely without ending the outer tx.
                if trans.nested and not trans._parent.nested:  # noqa: SLF001
                    sess.begin_nested()

            try:
                yield session
            finally:
                await session.close()
                await outer_tx.rollback()

