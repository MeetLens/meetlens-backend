"""
MeetLens Backend - FastAPI Application
Main entry point for the MeetLens MVP backend.
"""
import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models.messages import SummaryRequest, SummaryResponse
from services.summary_service import generate_summary
from endpoints.websocket import websocket_transcribe
from fastapi import WebSocket

# Load environment variables from .env for local development
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="MeetLens API",
    description="MeetLens MVP Backend - Real-time transcription, translation, and meeting summaries",
    version="0.1.0"
)

# CORS configuration (allow Flutter app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP: allow all origins; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Verify API keys are set
if not os.getenv("ELEVENLABS_API_KEY"):
    logger.warning("ELEVENLABS_API_KEY environment variable not set. Transcription will fail.")
if not os.getenv("OPENAI_API_KEY"):
    logger.warning("OPENAI_API_KEY environment variable not set. Translation and summary will fail.")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "MeetLens Backend", "version": "0.1.0"}


@app.post("/summary", response_model=SummaryResponse)
async def create_summary(request: SummaryRequest):
    """
    Generate meeting summary from full transcript.
    
    Endpoint: POST /summary
    Body: SummaryRequest (session_id, full_transcript, language)
    Returns: SummaryResponse (summary with short_overview, action_items, decisions)
    """
    # Validate request first (before calling service)
    if not request.full_transcript or not request.full_transcript.strip():
        raise HTTPException(
            status_code=400,
            detail="full_transcript is required and cannot be empty"
        )
    
    try:
        # Generate summary
        summary_block = await generate_summary(
            full_transcript=request.full_transcript,
            language=request.language
        )
        
        # Return response
        return SummaryResponse(summary=summary_block)
    
    except ValueError as e:
        logger.error(f"Invalid request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Summary generation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate summary"
        )


@app.websocket("/ws/transcribe")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time transcription and translation.
    
    Route: /ws/transcribe
    Handles: audio_chunk, end_session messages
    Streams: transcript_partial, transcript_stable, translation, error messages
    """
    await websocket_transcribe(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

