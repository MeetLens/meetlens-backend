"""
WebSocket endpoint for real-time transcription and translation.
Handles /ws/transcribe route according to API & Schema Contract.
"""
import base64
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect
from models.messages import (
    AudioChunkMessage,
    EndSessionMessage,
    TranscriptPartialMessage,
    TranscriptStableMessage,
    TranslationMessage,
    ErrorMessage
)
from services.session_manager import session_manager
from services.whisper_service import transcribe_audio
from services.transcript_merger import process_transcript
from services.translation_service import translate_segment

logger = logging.getLogger(__name__)

# Default languages for translation
DEFAULT_SOURCE_LANG = "en"
DEFAULT_TARGET_LANG = "tr"


async def websocket_transcribe(websocket: WebSocket):
    """
    WebSocket endpoint handler for /ws/transcribe.
    Processes audio chunks and streams transcript/translation messages.
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                message_dict = json.loads(data)
                message_type = message_dict.get("type")
                session_id = message_dict.get("session_id")
                
                if not session_id:
                    await _send_error(websocket, session_id or "unknown", "Missing session_id")
                    continue
                
                # Route by message type
                if message_type == "audio_chunk":
                    await _handle_audio_chunk(websocket, message_dict, session_id)
                elif message_type == "end_session":
                    await _handle_end_session(websocket, message_dict, session_id)
                else:
                    await _send_error(websocket, session_id, f"Unknown message type: {message_type}")
            
            except json.JSONDecodeError as e:
                await _send_error(websocket, "unknown", f"Invalid JSON: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                session_id = message_dict.get("session_id", "unknown") if 'message_dict' in locals() else "unknown"
                await _send_error(websocket, session_id, f"Processing error: {str(e)}")
    
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await _send_error(websocket, "unknown", f"Connection error: {str(e)}")
        except:
            pass


async def _handle_audio_chunk(websocket: WebSocket, message_dict: dict, session_id: str):
    """Handle audio_chunk message: transcribe, merge, translate, and stream responses."""
    try:
        # Parse and validate message
        audio_chunk_msg = AudioChunkMessage(**message_dict)
        
        # Get or create session state
        session_state = await session_manager.get_or_create(session_id)
        
        # Decode base64 audio data
        try:
            audio_bytes = base64.b64decode(audio_chunk_msg.data)
        except Exception as e:
            await _send_error(websocket, session_id, f"Failed to decode audio data: {str(e)}")
            return
        
        # Transcribe audio using Whisper (async)
        try:
            raw_transcript = await transcribe_audio(audio_bytes, audio_chunk_msg.audio_format)
        except Exception as e:
            logger.error(f"Whisper transcription failed for chunk {audio_chunk_msg.chunk_id}: {str(e)}")
            await _send_error(websocket, session_id, f"Transcription failed: {str(e)}", code="WHISPER_ERROR")
            return
        
        if not raw_transcript or not raw_transcript.strip():
            # Empty transcript (silence), skip processing
            logger.debug(f"Empty transcript from Whisper for chunk {audio_chunk_msg.chunk_id} - likely silence")
            return
        
        # Process transcript through merger
        partial_text, stable_segment = process_transcript(raw_transcript, session_state)
        
        # Update session state
        await session_manager.update(session_id, session_state)
        
        # Send transcript_partial if available
        if partial_text:
            partial_msg = TranscriptPartialMessage(
                type="transcript_partial",
                session_id=session_id,
                chunk_id=audio_chunk_msg.chunk_id,
                text=partial_text
            )
            await websocket.send_json(partial_msg.model_dump())
        
        # Send transcript_stable if available
        if stable_segment:
            stable_msg = TranscriptStableMessage(
                type="transcript_stable",
                session_id=session_id,
                text=stable_segment
            )
            await websocket.send_json(stable_msg.model_dump())
            
            # Translate stable segment
            try:
                translated_text = await translate_segment(
                    stable_segment,
                    source_lang=DEFAULT_SOURCE_LANG,
                    target_lang=DEFAULT_TARGET_LANG
                )
                
                if translated_text:
                    translation_msg = TranslationMessage(
                        type="translation",
                        session_id=session_id,
                        text=translated_text
                    )
                    await websocket.send_json(translation_msg.model_dump())
            
            except Exception as e:
                logger.error(f"Translation failed for segment: {str(e)}")
                # Don't send error to client for translation failures (non-critical)
    
    except Exception as e:
        logger.error(f"Error handling audio chunk: {str(e)}")
        await _send_error(websocket, session_id, f"Failed to process audio chunk: {str(e)}")


async def _handle_end_session(websocket: WebSocket, message_dict: dict, session_id: str):
    """Handle end_session message: finalize session state."""
    try:
        # Validate message
        end_session_msg = EndSessionMessage(**message_dict)
        
        # Finalize session
        session_state = await session_manager.finalize(session_id)
        
        if session_state:
            logger.info(f"Session {session_id} finalized. Full transcript length: {len(session_state.full_transcript)}")
        else:
            logger.warning(f"Session {session_id} not found for finalization")
        
        # Send acknowledgment (optional, not in spec but helpful)
        # Client will call /summary endpoint separately
    
    except Exception as e:
        logger.error(f"Error handling end_session: {str(e)}")
        await _send_error(websocket, session_id, f"Failed to end session: {str(e)}")


async def _send_error(websocket: WebSocket, session_id: str, message: str, code: str = None):
    """Send error message to client."""
    try:
        error_msg = ErrorMessage(
            type="error",
            session_id=session_id,
            message=message,
            code=code
        )
        await websocket.send_json(error_msg.model_dump())
    except Exception as e:
        logger.error(f"Failed to send error message: {str(e)}")

