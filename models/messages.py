"""
Pydantic models for WebSocket messages and HTTP requests/responses.
All models follow the API & Schema Contract specification.
"""
from typing import Literal, Optional, List
from pydantic import BaseModel


# WebSocket Message Models (Client → Server)
class AudioChunkMessage(BaseModel):
    type: Literal["audio_chunk"]
    session_id: str
    chunk_id: int
    audio_format: Literal["pcm_s16le_16k_mono"]
    data: str  # base64 encoded audio bytes


class EndSessionMessage(BaseModel):
    type: Literal["end_session"]
    session_id: str


# WebSocket Message Models (Server → Client)
class TranscriptPartialMessage(BaseModel):
    type: Literal["transcript_partial"]
    session_id: str
    chunk_id: int
    text: str


class TranscriptStableMessage(BaseModel):
    type: Literal["transcript_stable"]
    session_id: str
    text: str


class TranslationMessage(BaseModel):
    type: Literal["translation"]
    session_id: str
    text: str


class ErrorMessage(BaseModel):
    type: Literal["error"]
    session_id: str
    message: str
    code: Optional[str] = None


# HTTP Request/Response Models
class SummaryBlock(BaseModel):
    short_overview: str
    action_items: List[str]
    decisions: List[str]


class SummaryRequest(BaseModel):
    session_id: str
    full_transcript: str
    language: Optional[str] = None


class SummaryResponse(BaseModel):
    summary: SummaryBlock


# Internal Backend Models
class SessionState(BaseModel):
    session_id: str
    last_stable_text: str = ""
    tail_words: List[str] = []  # last N words for overlap detection
    buffer_unstable: str = ""  # unstable text from last chunk
    full_transcript: str = ""  # accumulated stable transcript

