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
from services.elevenlabs_service import elevenlabs_manager
from services.translation_service import (
    translate_segment,
    DEFAULT_SOURCE_LANG as TRANSLATION_SOURCE_LANG,
    DEFAULT_TARGET_LANG as TRANSLATION_TARGET_LANG,
)

logger = logging.getLogger(__name__)

# Default languages for translation (keeps in sync with translation_service env defaults)
DEFAULT_SOURCE_LANG = TRANSLATION_SOURCE_LANG
DEFAULT_TARGET_LANG = TRANSLATION_TARGET_LANG


async def websocket_transcribe(websocket: WebSocket):
    """
    WebSocket endpoint handler for /ws/transcribe.
    Processes audio chunks and streams transcript/translation messages.
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted")
    
    # Track active sessions for this WebSocket connection
    active_sessions = set()
    
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
                    await _handle_audio_chunk(websocket, message_dict, session_id, active_sessions)
                elif message_type == "end_session":
                    await _handle_end_session(websocket, message_dict, session_id, active_sessions)
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
    finally:
        # Cleanup: close all ElevenLabs sessions for this WebSocket connection
        for session_id in active_sessions:
            try:
                await elevenlabs_manager.close_session(session_id)
            except Exception as e:
                logger.error(f"Error closing ElevenLabs session {session_id} on disconnect: {str(e)}")


async def _handle_audio_chunk(websocket: WebSocket, message_dict: dict, session_id: str, active_sessions: set):
    """Handle audio_chunk message: forward to ElevenLabs and stream responses."""
    try:
        # Parse and validate message
        audio_chunk_msg = AudioChunkMessage(**message_dict)
        
        # Get or create session state (for full transcript accumulation)
        session_state = await session_manager.get_or_create(session_id)
        
        # Decode base64 audio data
        try:
            audio_bytes = base64.b64decode(audio_chunk_msg.data)
        except Exception as e:
            await _send_error(websocket, session_id, f"Failed to decode audio data: {str(e)}")
            return
        
        # Create event callback for ElevenLabs events
        async def event_callback(event_type: str, data: dict):
            """Callback to forward ElevenLabs events to MeetLens client."""
            try:
                logger.debug(f"Event callback called: event_type={event_type}, data={data}")
                if event_type == "transcript_partial":
                    partial_msg = TranscriptPartialMessage(
                        type="transcript_partial",
                        session_id=session_id,
                        chunk_id=data.get("chunk_id", audio_chunk_msg.chunk_id),
                        text=data.get("text", "")
                    )
                    logger.debug(f"Sending transcript_partial to client: chunk_id={partial_msg.chunk_id}, text='{partial_msg.text[:50]}...'")
                    await websocket.send_json(partial_msg.model_dump())

                    # Translate partial transcript for real-time display
                    partial_text = partial_msg.text.strip()
                    if partial_text:
                        try:
                            translated_partial = await translate_segment(
                                partial_text,
                                source_lang=DEFAULT_SOURCE_LANG,
                                target_lang=DEFAULT_TARGET_LANG
                            )
                            translated_partial = translated_partial.strip() if translated_partial else ""

                            if translated_partial:
                                previous_partial = session_state.partial_translation
                                if previous_partial and translated_partial.startswith(previous_partial):
                                    incremental_translation = translated_partial[len(previous_partial):].lstrip()
                                else:
                                    incremental_translation = translated_partial

                                session_state.partial_translation = translated_partial

                                if incremental_translation:
                                    translation_msg = TranslationMessage(
                                        type="translation",
                                        session_id=session_id,
                                        text=incremental_translation
                                    )
                                    logger.debug(
                                        "Sending incremental partial translation to client "
                                        f"(len={len(incremental_translation)})"
                                    )
                                    await websocket.send_json(translation_msg.model_dump())

                            await session_manager.update(session_id, session_state)
                        except Exception as e:
                            logger.error(f"Translation failed for partial segment: {str(e)}", exc_info=True)
                            await _send_error(
                                websocket,
                                session_id,
                                f"Translation failed: {str(e)}",
                                code="TRANSLATION_ERROR"
                            )

                elif event_type == "transcript_stable":
                    stable_text = data.get("text", "")
                    full_stable_text = data.get("full_text")
                    logger.info(f"Event callback received transcript_stable (incremental): '{stable_text[:100]}...'")
                    if stable_text:
                        stable_msg = TranscriptStableMessage(
                            type="transcript_stable",
                            session_id=session_id,
                            text=stable_text
                        )
                        logger.debug(f"Sending transcript_stable to client: '{stable_text[:100]}...'")
                        await websocket.send_json(stable_msg.model_dump())

                        # Update session state with stable transcript, allowing corrections from ElevenLabs
                        if full_stable_text:
                            # ElevenLabs may revise previous segments; trust the provided full text when available
                            if session_state.full_transcript and full_stable_text.startswith(session_state.full_transcript):
                                incremental_stable = full_stable_text[len(session_state.full_transcript):].lstrip()
                            else:
                                incremental_stable = None  # treat as corrected full transcript

                            session_state.full_transcript = full_stable_text
                        else:
                            incremental_stable = stable_text
                            session_state.full_transcript += " " + stable_text if session_state.full_transcript else stable_text

                        # Refresh translation using stable transcript (and clear partial state)
                        try:
                            logger.info(
                                f"Translating stable transcript for session {session_id} "
                                f"({len(session_state.full_transcript)} chars total) {DEFAULT_SOURCE_LANG}->{DEFAULT_TARGET_LANG}"
                            )

                            translation_increment = ""
                            if incremental_stable is not None and session_state.stable_translation:
                                # Append-only update
                                translated_increment = await translate_segment(
                                    incremental_stable,
                                    source_lang=DEFAULT_SOURCE_LANG,
                                    target_lang=DEFAULT_TARGET_LANG
                                )
                                translated_increment = translated_increment.strip() if translated_increment else ""
                                if translated_increment:
                                    translation_increment = translated_increment
                                    session_state.stable_translation = " ".join(
                                        filter(None, [session_state.stable_translation, translated_increment])
                                    ).strip()
                            else:
                                # Full retranslation to capture revisions
                                retranslated_full = await translate_segment(
                                    session_state.full_transcript,
                                    source_lang=DEFAULT_SOURCE_LANG,
                                    target_lang=DEFAULT_TARGET_LANG
                                )
                                retranslated_full = retranslated_full.strip() if retranslated_full else ""
                                if retranslated_full:
                                    if retranslated_full.startswith(session_state.stable_translation):
                                        translation_increment = retranslated_full[len(session_state.stable_translation):].lstrip()
                                    else:
                                        translation_increment = retranslated_full
                                    session_state.stable_translation = retranslated_full

                            session_state.partial_translation = ""
                            if translation_increment:
                                translation_msg = TranslationMessage(
                                    type="translation",
                                    session_id=session_id,
                                    text=translation_increment
                                )
                                logger.info(
                                    f"Sending translation increment to client (len={len(translation_increment)}): "
                                    f"'{translation_increment[:100]}...'"
                                )
                                await websocket.send_json(translation_msg.model_dump())

                            await session_manager.update(session_id, session_state)

                        except Exception as e:
                            logger.error(f"Translation failed for segment: {str(e)}", exc_info=True)
                            await _send_error(
                                websocket,
                                session_id,
                                f"Translation failed: {str(e)}",
                                code="TRANSLATION_ERROR"
                            )
                    else:
                        logger.warning(f"Received empty transcript_stable, skipping")
                
                elif event_type == "error":
                    logger.warning(f"Event callback received error: {data}")
                    await _send_error(
                        websocket,
                        session_id,
                        data.get("message", "Unknown error"),
                        code=data.get("code")
                    )
                else:
                    logger.warning(f"Unknown event_type in callback: {event_type}")
            
            except Exception as e:
                logger.error(f"Error in event callback: {str(e)}", exc_info=True)
        
        # Get or create ElevenLabs session
        try:
            logger.debug(f"Getting/creating ElevenLabs session for {session_id}, chunk_id: {audio_chunk_msg.chunk_id}, audio_size: {len(audio_bytes)} bytes")
            elevenlabs_session = await elevenlabs_manager.get_or_create_session(
                session_id,
                event_callback
            )
            active_sessions.add(session_id)
            
            # Send audio chunk to ElevenLabs
            logger.debug(f"Sending audio chunk {audio_chunk_msg.chunk_id} to ElevenLabs session {session_id}")
            await elevenlabs_session.send_audio_chunk(audio_bytes, audio_chunk_msg.chunk_id)
        
        except Exception as e:
            logger.error(f"ElevenLabs transcription failed for chunk {audio_chunk_msg.chunk_id}: {str(e)}", exc_info=True)
            await _send_error(websocket, session_id, f"Transcription failed: {str(e)}", code="ELEVENLABS_ERROR")
    
    except Exception as e:
        logger.error(f"Error handling audio chunk: {str(e)}")
        await _send_error(websocket, session_id, f"Failed to process audio chunk: {str(e)}")


async def _handle_end_session(websocket: WebSocket, message_dict: dict, session_id: str, active_sessions: set):
    """Handle end_session message: finalize session state and close ElevenLabs connection."""
    try:
        # Validate message
        end_session_msg = EndSessionMessage(**message_dict)
        
        # Close ElevenLabs session
        try:
            await elevenlabs_manager.close_session(session_id)
            active_sessions.discard(session_id)
        except Exception as e:
            logger.error(f"Error closing ElevenLabs session {session_id}: {str(e)}")
        
        # Finalize session state
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

