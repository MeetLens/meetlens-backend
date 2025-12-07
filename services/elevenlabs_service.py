"""
ElevenLabs Realtime STT Service for audio transcription using ElevenLabs Scribe v2 Realtime API.
Manages WebSocket connections to ElevenLabs and handles event mapping to MeetLens message types.
"""
import os
import json
import base64
import logging
import asyncio
from typing import Optional, Callable, Dict
from websockets.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException

logger = logging.getLogger(__name__)

# ElevenLabs API endpoint
ELEVENLABS_WS_URL = "wss://api.elevenlabs.io/v1/speech-to-text/realtime?model_id=scribe_v2_realtime"


class ElevenLabsRealtimeSession:
    """
    Manages a single ElevenLabs Realtime STT WebSocket session.
    Handles connection lifecycle, audio forwarding, and event mapping.
    """
    
    def __init__(self, session_id: str, api_key: str, event_callback: Callable):
        """
        Initialize ElevenLabs session.
        
        Args:
            session_id: MeetLens session ID
            api_key: ElevenLabs API key
            event_callback: Async callback function(event_type, data) to forward events to MeetLens client
        """
        self.session_id = session_id
        self.api_key = api_key
        self.event_callback = event_callback
        self.websocket = None
        self._connected = False
        self._closed = False
        self._receive_task = None
        self._chunk_id_counter = 0
        self._chunk_id_map: Dict[int, int] = {}  # Maps ElevenLabs event IDs to MeetLens chunk_ids
        self._current_chunk_id = 1  # Track current chunk_id for partial transcripts
        self._last_committed_text = ""  # Track last committed transcript for simple prefix-based diff
    
    async def connect(self):
        """Establish WebSocket connection to ElevenLabs."""
        if self._connected:
            logger.warning(f"Session {self.session_id} already connected")
            return
        
        try:
            # Connect to ElevenLabs WebSocket with authentication header
            self.websocket = await connect(
                ELEVENLABS_WS_URL,
                extra_headers={"xi-api-key": self.api_key}
            )
            self._connected = True
            logger.info(f"ElevenLabs session {self.session_id} connected")
            
            # Start receiving messages
            self._receive_task = asyncio.create_task(self._receive_loop())
            
        except Exception as e:
            logger.error(f"Failed to connect ElevenLabs session {self.session_id}: {str(e)}")
            self._connected = False
            raise
    
    def update_callback(self, event_callback: Callable):
        """Update the event callback for this session."""
        self.event_callback = event_callback
    
    async def send_audio_chunk(self, audio_bytes: bytes, chunk_id: int):
        """
        Send audio chunk to ElevenLabs.
        
        Args:
            audio_bytes: Raw PCM audio bytes (16kHz mono, 16-bit)
            chunk_id: MeetLens chunk ID for tracking
        """
        if not self._connected or self._closed:
            logger.warning(f"Cannot send audio chunk: session {self.session_id} not connected")
            return
        
        try:
            # Update current chunk_id for partial transcripts
            self._current_chunk_id = chunk_id
            
            # Encode audio bytes to base64 for JSON message
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            # Create input_audio_chunk message (ElevenLabs format)
            # Note: commit flag can be used to force commit, but we let ElevenLabs handle it automatically
            message = {
                "message_type": "input_audio_chunk",
                "audio_base_64": audio_base64,
                "sample_rate": 16000
            }
            
            # Store chunk_id mapping (we'll use a simple counter for ElevenLabs events)
            self._chunk_id_counter += 1
            self._chunk_id_map[self._chunk_id_counter] = chunk_id
            
            # Send message
            await self.websocket.send(json.dumps(message))
            logger.debug(f"Sent audio chunk {chunk_id} to ElevenLabs for session {self.session_id} (size: {len(audio_bytes)} bytes)")
            
        except Exception as e:
            logger.error(f"Failed to send audio chunk {chunk_id} to ElevenLabs: {str(e)}", exc_info=True)
            try:
                await self.event_callback("error", {
                    "message": f"Failed to send audio to transcription service: {str(e)}",
                    "code": "ELEVENLABS_SEND_ERROR"
                })
            except Exception as callback_error:
                logger.error(f"Error calling callback: {str(callback_error)}")
    
    async def _receive_loop(self):
        """Continuously receive and process messages from ElevenLabs."""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    logger.debug(f"ElevenLabs message received for session {self.session_id}: {json.dumps(data)}")
                    await self._handle_elevenlabs_event(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from ElevenLabs: {str(e)}, raw message: {message[:200]}")
                except Exception as e:
                    logger.error(f"Error processing ElevenLabs message: {str(e)}", exc_info=True)
        except ConnectionClosed:
            logger.info(f"ElevenLabs WebSocket closed for session {self.session_id}")
            self._connected = False
        except Exception as e:
            logger.error(f"ElevenLabs receive loop error for session {self.session_id}: {str(e)}", exc_info=True)
            self._connected = False
            try:
                await self.event_callback("error", {
                    "message": f"Transcription service connection error: {str(e)}",
                    "code": "ELEVENLABS_CONNECTION_ERROR"
                })
            except Exception as callback_error:
                logger.error(f"Error in event callback: {str(callback_error)}")
    
    async def _handle_elevenlabs_event(self, data: dict):
        """
        Handle events from ElevenLabs and map them to MeetLens message types.
        
        Event types:
        - partial_transcript: Interim transcription → transcript_partial
        - committed_transcript: Finalized segment → transcript_stable
        - error: Error event → error
        """
        # ElevenLabs uses "message_type" field
        event_type = data.get("message_type") or data.get("type")
        logger.debug(f"Processing ElevenLabs event type: {event_type} for session {self.session_id}")
        
        if event_type == "partial_transcript":
            # Map to transcript_partial ONLY - do NOT generate transcript_stable from partial events
            # ElevenLabs provides committed_transcript for stable segments, we should use that exclusively
            text = data.get("text", "").strip()
            logger.debug(f"ElevenLabs partial_transcript: '{text[:100]}...'")
            if text:
                # Use the current chunk_id
                chunk_id = self._current_chunk_id
                try:
                    await self.event_callback("transcript_partial", {
                        "chunk_id": chunk_id,
                        "text": text
                    })
                    # NO stable generation from partial - committed_transcript is the only source
                except Exception as e:
                    logger.error(f"Error calling event callback for partial_transcript: {str(e)}", exc_info=True)
        
        elif event_type == "committed_transcript":
            # This is the ONLY source of transcript_stable messages
            # Use simple prefix-based diff: if current_text starts with last_committed_text, extract suffix
            text = data.get("text", "").strip()
            logger.debug(f"ElevenLabs committed_transcript: '{text[:100]}...' (last_committed: '{self._last_committed_text[:50] if self._last_committed_text else 'None'}...')")
            if text:
                try:
                    # Simple prefix-based diff: extract only new portion
                    if not self._last_committed_text:
                        # First commit, send everything
                        new_text = text
                    elif text.startswith(self._last_committed_text):
                        # Current text extends previous, extract only new suffix
                        new_text = text[len(self._last_committed_text):].strip()
                        # Remove leading space if present
                        if new_text.startswith(' '):
                            new_text = new_text[1:]
                    else:
                        # Text doesn't start with previous (might be correction or reset)
                        # Send full text but log it
                        logger.debug(f"Committed text doesn't start with previous (possible correction/reset). Previous: '{self._last_committed_text[:50]}...', Current: '{text[:50]}...'")
                        new_text = text
                    
                    if new_text and len(new_text.strip()) > 0:
                        logger.info(f"Sending incremental stable from committed_transcript: '{new_text[:100]}...'")
                        await self.event_callback("transcript_stable", {
                            "text": new_text
                        })
                        # Update last_committed_text to FULL current text for next diff
                        self._last_committed_text = text
                    else:
                        logger.debug(f"Skipping empty/duplicate committed_transcript")
                except Exception as e:
                    logger.error(f"Error calling event callback for committed_transcript: {str(e)}", exc_info=True)
        
        elif event_type == "error":
            # Map to error
            error_message = data.get("message", "Unknown error from transcription service")
            error_code = data.get("code", "ELEVENLABS_ERROR")
            logger.warning(f"ElevenLabs error: {error_message} (code: {error_code})")
            
            # Handle "insufficient audio activity" gracefully (don't send as error)
            if "insufficient audio" in error_message.lower() or "no audio" in error_message.lower():
                logger.debug(f"ElevenLabs: {error_message} (non-critical)")
                return
            
            try:
                await self.event_callback("error", {
                    "message": error_message,
                    "code": error_code
                })
            except Exception as e:
                logger.error(f"Error calling event callback for error: {str(e)}", exc_info=True)
        
        elif event_type == "session_started":
            # Session started event - just log it, no action needed
            logger.info(f"ElevenLabs session started for {self.session_id}")
        
        else:
            # Unknown event type - log but don't forward
            logger.warning(f"Unknown ElevenLabs event type: {event_type}, full data: {json.dumps(data)}")
    
    async def close(self):
        """Gracefully close the ElevenLabs WebSocket connection."""
        if self._closed:
            return
        
        self._closed = True
        
        try:
            # Cancel receive task
            if self._receive_task and not self._receive_task.done():
                self._receive_task.cancel()
                try:
                    await self._receive_task
                except asyncio.CancelledError:
                    pass
            
            # Close WebSocket
            if self.websocket and self._connected:
                await self.websocket.close()
                self._connected = False
            
            logger.info(f"ElevenLabs session {self.session_id} closed")
            
        except Exception as e:
            logger.error(f"Error closing ElevenLabs session {self.session_id}: {str(e)}")
    
    def is_connected(self) -> bool:
        """Check if session is connected."""
        return self._connected and not self._closed
    


class ElevenLabsSessionManager:
    """
    Manages multiple ElevenLabs Realtime sessions, one per MeetLens session_id.
    """
    
    def __init__(self):
        self._sessions: Dict[str, ElevenLabsRealtimeSession] = {}
        self._lock = asyncio.Lock()
        self._api_key: Optional[str] = None
    
    def _get_api_key(self) -> str:
        """Get ElevenLabs API key from environment."""
        if not self._api_key:
            api_key = os.getenv("ELEVENLABS_API_KEY")
            if not api_key:
                raise ValueError("ELEVENLABS_API_KEY environment variable is not set")
            self._api_key = api_key
        return self._api_key
    
    async def get_or_create_session(
        self,
        session_id: str,
        event_callback: Callable
    ) -> ElevenLabsRealtimeSession:
        """
        Get existing session or create a new one.
        
        Args:
            session_id: MeetLens session ID
            event_callback: Callback function(event_type, data) for forwarding events
        
        Returns:
            ElevenLabsRealtimeSession instance
        """
        async with self._lock:
            if session_id not in self._sessions:
                api_key = self._get_api_key()
                session = ElevenLabsRealtimeSession(session_id, api_key, event_callback)
                self._sessions[session_id] = session
                
                # Connect the session
                try:
                    await session.connect()
                except Exception as e:
                    logger.error(f"Failed to create ElevenLabs session {session_id}: {str(e)}")
                    # Remove failed session
                    del self._sessions[session_id]
                    raise
            else:
                # Update callback for existing session
                self._sessions[session_id].update_callback(event_callback)
            
            return self._sessions[session_id]
    
    async def close_session(self, session_id: str):
        """Close and remove a session."""
        async with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                await session.close()
                del self._sessions[session_id]
                logger.info(f"Closed and removed ElevenLabs session {session_id}")
    
    async def get_session(self, session_id: str) -> Optional[ElevenLabsRealtimeSession]:
        """Get existing session if it exists."""
        async with self._lock:
            return self._sessions.get(session_id)


# Global session manager instance
elevenlabs_manager = ElevenLabsSessionManager()

