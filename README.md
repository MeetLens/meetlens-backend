# MeetLens Backend

The FastAPI-based backend for the MeetLens MVP. This service provides real-time transcription, translation, and AI-powered meeting summaries using WebSockets and OpenAI.

## Features

- **Real-time Transcription & Translation**: Handles audio streams via WebSockets (`/ws/transcribe`).
- **Meeting Summaries**: Generates comprehensive summaries, action items, and key decisions using OpenAI GPT models (`/summary`).
- **Health Check**: Simple endpoint to verify service status (`/`).
- **CORS Support**: Configured to support cross-origin requests (e.g., from Flutter apps).

## Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Runtime**: Python 3.9+
- **AI/LLM**: OpenAI API
- **Networking**: WebSockets, Uvicorn (ASGI)
- **Testing**: Pytest

## Prerequisites

- Python 3.9 or higher
- OpenAI API Key

## Installation

1. **Clone the repository** (if not already done):
   ```sh
   git clone <repository-url>
   cd meetlens-backend
   ```

2. **Create and activate a virtual environment**:
   ```sh
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```sh
   pip install -r requirements.txt
   ```

## Configuration

1. Create a `.env` file in the root directory:
   ```sh
   touch .env
   ```

2. Add your OpenAI API key to `.env`:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   ```

## Usage

### Running the Server

Start the application using Uvicorn:

```sh
python main.py
# OR
uvicorn main:app --reload
```

The server will start at `http://0.0.0.0:8000`.

### API Documentation

Interactive API documentation is available at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Key Endpoints

- **WebSocket**: `ws://localhost:8000/ws/transcribe`
- **Generate Summary**: `POST /summary`
    - Body:
      ```json
      {
        "session_id": "optional-uuid",
        "full_transcript": "Meeting text content...",
        "language": "en"
      }
      ```

## Testing

Run the test suite using `pytest`:

```sh
pytest
```
