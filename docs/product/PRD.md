# Product Requirements Document: MeetLens Backend

**Version:** 1.0
**Date:** December 12, 2024
**Status:** Implemented
**Platform:** DigitalOcean App Platform (Python/FastAPI)

---

## Executive Summary

MeetLens Backend is a production-ready FastAPI application that provides **real-time meeting transcription, translation, and AI-powered summarization** services for globally distributed teams conducting multilingual meetings. The system enables seamless collaboration through live speech-to-text conversion (powered by ElevenLabs Scribe v2), asynchronous multi-language translation (OpenAI GPT), and intelligent meeting summaries with action items and decisions.

**Key Value Propositions:**
- Real-time audio transcription with sub-second latency
- Live multi-language translation for meeting participants
- AI-generated structured summaries with actionable insights
- WebSocket-based streaming for immediate feedback
- Scalable architecture ready for production deployment

---

## Product Overview

### Target Users
- **Meeting Organizers**: Schedule and manage multilingual meetings
- **Meeting Participants**: Receive real-time transcriptions and translations
- **Application Integrators**: Developers building on top of MeetLens API

### Core Capabilities

1. **Real-Time Transcription** (`/ws/transcribe`)
   - WebSocket endpoint for bidirectional audio streaming
   - Accepts PCM audio chunks (16kHz, mono, 16-bit)
   - Returns partial (interim) and stable (finalized) transcripts
   - Powered by ElevenLabs Scribe v2 Realtime API

2. **Live Translation** (Integrated in WebSocket flow)
   - Translates transcripts in real-time
   - Supports both partial (streaming) and stable (finalized) translations
   - Configurable source/target languages (default: en → tr)
   - Powered by OpenAI GPT-4.1-mini

3. **Meeting Summaries** (`POST /summary`)
   - Generates structured summaries from full transcripts
   - Extracts short overview, action items, and decisions
   - Supports multiple languages
   - Powered by OpenAI GPT-5-nano

4. **Session Management**
   - Maintains per-session state for transcript accumulation
   - In-memory storage (can be extended to Redis)
   - Thread-safe async operations

---

## System Architecture

See [Architecture Flow](../architecture/FLOW.md) for detailed diagrams and component breakdowns.

---

## Technical Stack

### Runtime & Framework
- **Python**: 3.9+
- **FastAPI**: 0.123.10 (ASGI web framework)
- **Uvicorn**: ASGI server
- **WebSockets**: 12.0 (WebSocket client/server)

### AI/LLM Services
- **ElevenLabs Scribe v2 Realtime**: Real-time speech-to-text transcription
- **OpenAI GPT-4.1-mini**: Translation service
- **OpenAI GPT-5-nano**: Summary generation
- **OpenAI Whisper-1**: Audio transcription (legacy/fallback)

### Core Dependencies
```
fastapi==0.123.10
openai==2.9.0
websockets==12.0
python-dotenv==1.2.1
pydantic (via FastAPI)
```

### Deployment Target
- **Platform**: DigitalOcean App Platform
- **Region**: NYC (configurable)
- **Instance**: basic-xxs (1 instance)
- **Port**: 8080
- **Health Check**: `GET /`

---

## API Specification

See [API & Schema Contract](../api/CONTRACT.md) for full REST and WebSocket protocol details.

---

## Data Models

See [API & Schema Contract](../api/CONTRACT.md#data-models).

---

## Service Components

See [Architecture Flow](../architecture/FLOW.md#5-backend-components).

---

## WebSocket Event Flow

See [Architecture Flow](../architecture/FLOW.md#3-runtime-flow--step-by-step).

---

## Translation Processing Details

See [Architecture Flow](../architecture/FLOW.md#35-translation-flow).

---

## Environment Configuration

### Required Environment Variables

```bash
# OpenAI API (Required)
OPENAI_API_KEY=sk-...

# ElevenLabs API (Required)
ELEVENLABS_API_KEY=...

# Optional Configuration
SOURCE_LANGUAGE=en          # Default: en
TARGET_LANGUAGE=tr          # Default: tr
TRANSLATION_MODEL=gpt-4.1-mini  # Default: gpt-4.1-mini
PORT=8080                   # Default: 8080
```

### DigitalOcean App Platform Configuration

**Environment Variables (Secrets):**
- `OPENAI_API_KEY`: (Secret)
- `ELEVENLABS_API_KEY`: (Secret)
- `PORT`: 8080

**Build Settings:**
- **Runtime**: Python 3.9+
- **Build Command**: (none, uses Procfile)
- **Run Command**: `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}`

**Health Check:**
- **Path**: `/`
- **Port**: 8080
- **Initial Delay**: 10s
- **Period**: 10s
- **Timeout**: 5s

---

## Deployment

### DigitalOcean App Platform (Current)

**Configuration File:** `.do/app.yaml`

```yaml
name: meetlens-backend
region: nyc

services:
  - name: api
    github:
      repo: MeetLens/meetlens-backend
      branch: main
      deploy_on_push: true

    run_command: uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
    environment_slug: python
    http_port: 8080

    health_check:
      http_path: /
      initial_delay_seconds: 10
      period_seconds: 10

    envs:
      - key: OPENAI_API_KEY
        scope: RUN_TIME
        type: SECRET
      - key: ELEVENLABS_API_KEY
        scope: RUN_TIME
        type: SECRET

    instance_count: 1
    instance_size_slug: basic-xxs
```

**Deployment Steps:**

1. **Via Web UI:**
   - Navigate to DigitalOcean App Platform dashboard
   - Create App → Connect GitHub repo
   - Configure environment variables
   - Deploy

2. **Via CLI (if `doctl` installed):**
   ```bash
   doctl apps create --spec .do/app.yaml
   doctl apps list
   doctl apps logs <app-id>
   ```

---

## Error Handling & Resilience

### OpenAI API Errors

**Rate Limiting:**
- Translation: Falls back to source text
- Summary: Falls back to transcript as overview
- Logged as warnings, not errors

**Timeouts:**
- Same fallback behavior as rate limiting
- Client receives partial results

**API Errors:**
- Logged as errors
- Sent to client as `error` messages
- HTTP 500 response for REST endpoints

### ElevenLabs API Errors

**Connection Failures:**
- Logged and sent to client as `ELEVENLABS_CONNECTION_ERROR`
- Session remains in failed state
- Client should reconnect

**Transcription Errors:**
- "Insufficient audio activity" errors are suppressed (non-critical)
- Other errors forwarded to client

**WebSocket Disconnects:**
- Logged as info (expected on client disconnect)
- Sessions cleaned up automatically

---

## Performance & Scalability

### Current Limitations (MVP)

- **In-Memory State**: Session state not persisted across restarts
- **Single Instance**: No horizontal scaling support yet
- **No Load Balancing**: Single instance deployment

### Performance Characteristics

- **Transcription Latency**: Sub-second (ElevenLabs Scribe v2)
- **Translation Latency**: 1-3 seconds (async, non-blocking)
- **Summary Generation**: 3-10 seconds (depends on transcript length)
- **WebSocket Concurrency**: FastAPI async handles multiple connections

### Future Scalability Enhancements

1. **Redis Session Storage**
   - Replace in-memory `SessionManager` with Redis backend
   - Enable multi-instance deployments
   - Persist sessions across restarts

2. **Load Balancing**
   - Deploy multiple app instances
   - Use DigitalOcean Load Balancer
   - Sticky sessions for WebSocket connections

3. **Database Integration**
   - Store meeting transcripts/translations
   - Enable historical queries
   - Support analytics

4. **Message Queue**
   - Queue translation tasks
   - Decouple translation from transcription
   - Retry failed translations

---

## Testing

### Test Coverage

**Unit Tests:**
- `test_session_state.py`: Session state management
- `test_transcript_merger.py`: Transcript merging logic
- `test_summary_endpoint.py`: Summary generation endpoint
- `test_usage_tracker.py`: OpenAI usage tracking
- `test_ws_transcribe.py`: WebSocket message handling

**Integration Tests:**
- `test_integration_mvp.py`: End-to-end WebSocket flow

**Running Tests:**
```bash
pytest
pytest -v  # Verbose output
pytest tests/test_summary_endpoint.py  # Single test file
```

---

## Dependencies

### Core Dependencies

```
fastapi==0.123.10          # ASGI web framework
uvicorn==0.22.1            # ASGI server (implied)
openai==2.9.0              # OpenAI API client
websockets==12.0           # WebSocket client/server
python-dotenv==1.2.1       # Environment variable loading
pydantic                   # Data validation (via FastAPI)
```

### Testing Dependencies

```
pytest==latest
pytest-asyncio==0.21.1     # Async test support
pytest-mock==3.12.0        # Mocking utilities
```

### Optional/Utility Dependencies

```
httptools==0.7.1           # HTTP parsing (performance)
uvloop==0.22.1             # Fast event loop (performance)
watchfiles==1.1.1          # File watching (dev mode)
email-validator==2.3.0     # Email validation
python-multipart==0.0.20   # Multipart form parsing
```

---

## API Usage Examples

### WebSocket Client (Python)

```python
import asyncio
import websockets
import json
import base64

async def transcribe_audio():
    uri = "ws://localhost:8000/ws/transcribe"
    async with websockets.connect(uri) as websocket:
        # Send audio chunks
        for chunk_id, audio_bytes in enumerate(audio_stream, start=1):
            message = {
                "type": "audio_chunk",
                "session_id": "session-123",
                "chunk_id": chunk_id,
                "audio_format": "pcm_s16le_16k_mono",
                "data": base64.b64encode(audio_bytes).decode()
            }
            await websocket.send(json.dumps(message))

            # Receive and process responses
            response = await websocket.recv()
            data = json.loads(response)
            print(f"Received: {data['type']} - {data.get('text', '')}")

        # End session
        await websocket.send(json.dumps({
            "type": "end_session",
            "session_id": "session-123"
        }))

asyncio.run(transcribe_audio())
```

### Summary Generation (cURL)

```bash
curl -X POST http://localhost:8000/summary \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-123",
    "full_transcript": "Discussion about Q4 roadmap and feature priorities...",
    "language": "en"
  }'
```

**Response:**
```json
{
  "summary": {
    "short_overview": "The team discussed Q4 roadmap priorities...",
    "action_items": [
      "Schedule architecture review meeting",
      "Update project timeline"
    ],
    "decisions": [
      "Prioritize feature X over feature Y",
      "Allocate 2 engineers to backend work"
    ]
  }
}
```

---

## Monitoring & Observability

### Logging

**Log Levels:**
- `INFO`: Connection events, session lifecycle, API calls
- `DEBUG`: Detailed event flow, message contents
- `WARNING`: Rate limits, timeouts, non-critical errors
- `ERROR`: API failures, connection errors

**Log Format:**
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

**Key Log Events:**
- WebSocket connection accepted/disconnected
- ElevenLabs session created/closed
- Transcription partial/stable received
- Translation started/completed
- Summary generation started/completed
- Error conditions

### Usage Tracking

**Tracked Metrics:**
- OpenAI API usage (tokens, requests)
- Request types (translation, summary)
- Model usage (gpt-4.1-mini, gpt-5-nano)

**Future Enhancements:**
- Prometheus metrics endpoint
- DigitalOcean monitoring integration
- Error rate tracking
- Latency percentiles

---

## Security Considerations

### API Key Management

- API keys stored as environment variables
- Marked as secrets in deployment configuration
- Never logged or exposed in responses
- Validated on application startup

### CORS Configuration

**Current (MVP):**
```python
allow_origins=["*"]  # Allow all origins
```

**Production Recommendation:**
```python
allow_origins=[
    "https://meetlens.app",
    "https://app.meetlens.com"
]
```

### WebSocket Security

- No authentication implemented (MVP)
- Recommendation: Add JWT-based auth
- Validate session_id format
- Rate limiting per session

### Input Validation

- Pydantic models validate all input
- Audio format validation
- Transcript length limits (future)
- Session ID format validation (future)

---

## Future Enhancements

### Short-Term (Next 3 Months)

1. **Redis Session Storage**
   - Persist sessions across restarts
   - Enable horizontal scaling

2. **Authentication & Authorization**
   - JWT-based WebSocket auth
   - API key management for REST endpoints

3. **Rate Limiting**
   - Per-session rate limits
   - API usage quotas

4. **Enhanced Error Recovery**
   - Automatic ElevenLabs reconnection
   - Translation retry logic

### Medium-Term (3-6 Months)

1. **Database Integration**
   - PostgreSQL for meeting data
   - Store transcripts, translations, summaries
   - Historical query support

2. **Multi-Language Support**
   - Configurable per-session languages
   - Support 10+ languages

3. **Advanced Analytics**
   - Meeting duration tracking
   - Speaker identification
   - Sentiment analysis

4. **WebRTC Integration**
   - Direct audio capture from browser
   - Eliminate client-side audio processing

### Long-Term (6-12 Months)

1. **Speaker Diarization**
   - Identify multiple speakers
   - Per-speaker transcripts

2. **Meeting Recording**
   - Store raw audio
   - Playback with synchronized captions

3. **Mobile SDKs**
   - iOS/Android native libraries
   - React Native support

4. **Enterprise Features**
   - Multi-tenant support
   - Custom vocabulary/jargon
   - Compliance (GDPR, HIPAA)

---

## Appendix

### File Structure

```
meetlens-backend/
├── main.py                     # FastAPI application entry point
├── Procfile                    # DigitalOcean run command
├── requirements.txt            # Python dependencies
├── README.md                   # Setup and deployment guide
├── PRD.md                      # This document
├── .env                        # Local environment variables (git-ignored)
├── .do/
│   └── app.yaml               # DigitalOcean deployment config
├── models/
│   ├── __init__.py
│   └── messages.py            # Pydantic data models
├── endpoints/
│   ├── __init__.py
│   └── websocket.py           # WebSocket endpoint handler
├── services/
│   ├── __init__.py
│   ├── elevenlabs_service.py  # ElevenLabs WebSocket client
│   ├── session_manager.py     # Session state management
│   ├── translation_service.py # OpenAI translation
│   ├── summary_service.py     # OpenAI summarization
│   ├── whisper_service.py     # OpenAI Whisper (legacy)
│   ├── usage_tracker.py       # API usage tracking
│   └── transcript_merger.py   # Transcript merging logic
└── tests/
    ├── __init__.py
    ├── conftest.py            # Pytest configuration
    ├── test_session_state.py
    ├── test_transcript_merger.py
    ├── test_summary_endpoint.py
    ├── test_usage_tracker.py
    ├── test_ws_transcribe.py
    └── test_integration_mvp.py
```

### Glossary

- **Partial Transcript**: Interim transcription that may be revised
- **Stable Transcript**: Finalized transcription that won't change
- **Incremental Message**: Message containing only new text since last update
- **Session State**: Per-session data maintained throughout meeting
- **ElevenLabs Scribe v2**: Real-time speech-to-text API
- **OpenAI GPT**: Large language model for translation/summarization
- **ASGI**: Asynchronous Server Gateway Interface (FastAPI protocol)
- **PCM**: Pulse Code Modulation (raw audio format)

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-12-12 | System | Initial PRD based on implemented codebase |

---

**End of Document**
