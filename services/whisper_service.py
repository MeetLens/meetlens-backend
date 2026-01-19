"""
Whisper Service for audio transcription using OpenAI Whisper API.
Handles PCM audio format conversion and API calls.

NOTE: This service is NOT used in the current MVP implementation.
The MVP uses ElevenLabs Scribe v2 Realtime API for transcription instead.

This implementation is kept as an alternative option for:
- Cost optimization (Whisper may be cheaper for batch processing)
- Fallback if ElevenLabs becomes unavailable
- On-device transcription in future "Pro/Offline" mode

Current implementation: See services/elevenlabs_service.py
"""
import os
import base64
import io
import wave
import logging
from openai import APIError, APITimeoutError, OpenAI, RateLimitError

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


async def transcribe_audio(audio_bytes: bytes, audio_format: str) -> str:
    """
    Transcribe audio bytes using OpenAI Whisper API.
    
    Args:
        audio_bytes: Raw audio bytes (PCM format)
        audio_format: Audio format string (e.g., "pcm_s16le_16k_mono")
    
    Returns:
        Transcribed text string

    Raises:
        APIError: If the OpenAI API returns an error response
        RateLimitError: If request is rate limited (returns empty transcript for retry)
        APITimeoutError: If OpenAI request times out (returns empty transcript for retry)
    """
    import asyncio
    
    try:
        # Convert PCM bytes to WAV format for Whisper API
        # Format: pcm_s16le_16k_mono = 16-bit signed little-endian, 16kHz, mono
        wav_bytes = _pcm_to_wav(audio_bytes, sample_rate=16000, channels=1, sample_width=2)

        # Create a file-like object from bytes
        audio_file = io.BytesIO(wav_bytes)
        audio_file.name = "audio.wav"

        # Call OpenAI Whisper API (run sync call in executor to avoid blocking)
        client = _get_client()

        # Run the synchronous API call in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        transcript = await loop.run_in_executor(
            None,
            lambda: client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
        )

        # Handle both string and object responses
        if isinstance(transcript, str):
            return transcript.strip()
        else:
            return str(transcript).strip()

    except RateLimitError as e:
        logger.warning("Whisper transcription rate limited; returning empty transcript fallback: %s", e)
        return ""
    except APITimeoutError as e:
        logger.warning("Whisper transcription timed out; returning empty transcript fallback: %s", e)
        return ""
    except APIError as e:
        logger.error("Whisper transcription API error: %s", e)
        raise
    except Exception as e:
        logger.error(f"Whisper transcription failed: {str(e)}")
        raise


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int, channels: int, sample_width: int) -> bytes:
    """
    Convert PCM audio bytes to WAV format.
    
    Args:
        pcm_bytes: Raw PCM audio data
        sample_rate: Sample rate in Hz (e.g., 16000)
        channels: Number of channels (1 for mono, 2 for stereo)
        sample_width: Sample width in bytes (2 for 16-bit)
    
    Returns:
        WAV format bytes
    """
    wav_buffer = io.BytesIO()
    
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    
    wav_buffer.seek(0)
    return wav_buffer.read()

