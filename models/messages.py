"""
Pydantic models for WebSocket messages and HTTP requests/responses.
All models follow the API & Schema Contract specification.
"""
from typing import Literal, Optional, List
from pydantic import BaseModel, Field


# WebSocket Message Models (Client → Server)
class AudioChunkMessage(BaseModel):
    type: Literal["audio_chunk"]
    session_id: str
    chunk_id: int
    audio_format: Literal["pcm_s16le_16k_mono"]
    data: str  # base64 encoded audio bytes
    target_lang: Optional[str] = None


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


class TranslationPartialMessage(BaseModel):
    type: Literal["translation_partial"]
    session_id: str
    chunk_id: int
    text: str


class TranslationStableMessage(BaseModel):
    type: Literal["translation_stable"]
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
    tail_words: List[str] = Field(default_factory=list)
    buffer_unstable: str = ""
    full_transcript: str = ""  # accumulated stable transcript (from ElevenLabs committed_transcript events)
    stable_translation: str = ""  # accumulated stable translation text
    partial_translation: str = ""  # latest partial translation for the current unstable segment
    target_lang: Optional[str] = None
