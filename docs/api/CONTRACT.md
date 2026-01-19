# API & Schema Contract

This document specifies the REST and WebSocket protocols used by MeetLens Backend.

## REST Endpoints

### 1. Health Check

**Endpoint:** `GET /`

**Response:**
```json
{
  "status": "ok",
  "service": "MeetLens Backend",
  "version": "0.1.0"
}
```

### 2. Generate Meeting Summary

**Endpoint:** `POST /summary`

**Request Body:**
```json
{
  "session_id": "string (UUID recommended)",
  "full_transcript": "string (required, non-empty)",
  "language": "string (optional, e.g., 'en', 'tr')"
}
```

**Response (200 OK):**
```json
{
  "summary": {
    "short_overview": "Brief 2-5 sentence overview of the meeting",
    "action_items": [
      "Action item 1",
      "Action item 2"
    ],
    "decisions": [
      "Decision 1",
      "Decision 2"
    ]
  }
}
```

**Error Responses:**
- `400 Bad Request`: Empty transcript or validation error
- `500 Internal Server Error`: AI processing failure

---

## WebSocket Protocol

**Endpoint:** `ws://[host]/ws/transcribe`

**Connection Flow:**
1. Client connects to WebSocket endpoint
2. Server accepts connection
3. Client sends audio chunks and session control messages
4. Server streams transcription and translation events
5. Client ends session when meeting concludes

---

### Client → Server Messages

#### 1. Audio Chunk Message

Sent continuously during active audio recording.

```json
{
  "type": "audio_chunk",
  "session_id": "string (UUID)",
  "chunk_id": "integer (sequential)",
  "audio_format": "pcm_s16le_16k_mono",
  "data": "base64-encoded audio bytes"
}
```

**Audio Format Requirements:**
- **Encoding**: PCM signed 16-bit little-endian
- **Sample Rate**: 16kHz
- **Channels**: Mono
- **Sample Width**: 2 bytes (16-bit)

#### 2. End Session Message

Sent when meeting ends or user stops recording.

```json
{
  "type": "end_session",
  "session_id": "string (UUID)"
}
```

---

### Server → Client Messages

#### 1. Transcript Partial (Interim)

Streaming partial transcription for real-time display.

```json
{
  "type": "transcript_partial",
  "session_id": "string",
  "chunk_id": "integer",
  "text": "partial transcription text..."
}
```

**Behavior:**
- Sent continuously as speech is detected
- Text may be revised in subsequent partial messages
- Not guaranteed to be final
- Use for live captions

#### 2. Transcript Stable (Finalized)

Committed transcription segment (will not change).

```json
{
  "type": "transcript_stable",
  "session_id": "string",
  "text": "finalized transcription segment"
}
```

**Behavior:**
- Sent when ElevenLabs commits a transcript segment
- Text is final and won't be revised
- Incremental (only new text since last stable message)
- Accumulate for full transcript

#### 3. Translation Partial (Interim)

Streaming partial translation for real-time display.

```json
{
  "type": "translation_partial",
  "session_id": "string",
  "chunk_id": "integer",
  "text": "partial translation text..."
}
```

**Behavior:**
- Async translation of partial transcripts
- May be revised as partial transcript updates
- Incremental (only new translated text)
- Use for live translated captions

#### 4. Translation Stable (Finalized)

Committed translation segment (based on stable transcript).

```json
{
  "type": "translation_stable",
  "session_id": "string",
  "text": "finalized translation segment"
}
```

**Behavior:**
- Sent after stable transcript is translated
- Text is final (unless full retranslation occurs)
- Incremental (only new text since last stable translation)
- Accumulate for full translated transcript

#### 5. Error Message

Error notification during transcription/translation.

```json
{
  "type": "error",
  "session_id": "string",
  "message": "Error description",
  "code": "ERROR_CODE (optional)"
}
```

**Common Error Codes:**
- `ELEVENLABS_ERROR`: ElevenLabs API error
- `ELEVENLABS_SEND_ERROR`: Failed to send audio to ElevenLabs
- `ELEVENLABS_CONNECTION_ERROR`: WebSocket connection failure
- `TRANSLATION_ERROR`: Translation service failure

---

## Data Models

### Session State (Internal)

Maintains per-session state throughout a meeting.

```python
class SessionState(BaseModel):
    session_id: str
    last_stable_text: str = ""
    tail_words: List[str] = []      # overlap için son N kelime
    buffer_unstable: str = ""      # son chunk’tan gelen unstable parça
    full_transcript: str = ""      # tüm stable transcript
    stable_translation: str = ""         # accumulated stable translation text
    partial_translation: str = ""        # latest partial translation for current unstable segment
```

**Lifecycle:**
1. Created on first `audio_chunk` for session
2. Updated as transcription progresses
3. Finalized on `end_session`
4. Persisted in-memory (can be extended to Redis)
