# MeetLens Backend

The FastAPI-based backend for the MeetLens MVP. This service provides real-time transcription, translation, and AI-powered meeting summaries using WebSockets, ElevenLabs, and OpenAI.

## 📋 Documentation Index

### Product & Requirements
- [Product Requirements Document (PRD)](docs/product/PRD.md) - Core vision and scope
- [Product Positioning](docs/product/POSITIONING.md) - Target audience and value prop
- [MVP Acceptance Criteria](docs/product/ACCEPTANCE_CRITERIA.md) - Success definitions

### Technical Architecture
- [Architecture Flow](docs/architecture/FLOW.md) - System design and sequence diagrams
- [API & Schema Contract](docs/api/CONTRACT.md) - REST and WebSocket protocol details
- [Schema Diagram](docs/architecture/SCHEMA_DIAGRAM.md) - Database relationship visualization

### Database
- [Database Setup & Quick Start](docs/database/SETUP.md) - **Start here for development**
- [Database Overview](docs/database/OVERVIEW.md) - Detailed schema reference
- [Implementation Summary](docs/database/IMPLEMENTATION_SUMMARY.md) - Current state of DB layer

### Development
- [Masterprompt](docs/development/MASTERPROMPT.md) - System instructions for AI agents
- [Documentation Update Summary](docs/development/UPDATE_SUMMARY.md) - Recent changes log

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- ElevenLabs API Key
- OpenAI API Key

### Installation & Setup
For detailed setup instructions, including database configuration, see the [Database Setup & Quick Start](docs/database/SETUP.md) guide.

1. **Clone and Install**:
   ```bash
   git clone <repository-url>
   cd meetlens-backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configuration**:
   Create a `.env` file with your keys:
   ```env
   ELEVENLABS_API_KEY=your_key
   OPENAI_API_KEY=your_key
   ```

3. **Run the Server**:
   ```bash
   fastapi dev main.py
   ```
   The server will start at `http://localhost:8000`.

### Key Endpoints
- **WebSocket**: `ws://localhost:8000/ws/transcribe`
- **REST Summary**: `POST /summary`
- **API Docs**: `http://localhost:8000/docs`

---

## 🛠 Tech Stack
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Transcription**: ElevenLabs Scribe v2 Realtime API
- **Translation & Summarization**: OpenAI GPT API
- **Networking**: WebSockets, Uvicorn (ASGI)
- **Database**: PostgreSQL (SQLAlchemy 2.0 Async, Alembic)

---

## 🧪 Testing
```bash
# Run all tests
pytest

# Run database tests only
pytest tests/test_database_schema.py tests/test_auth_flows.py -v
```

---

## 🚢 Deployment
MeetLens Backend is designed for [DigitalOcean App Platform](https://www.digitalocean.com/products/app-platform/). See the [PRD](docs/product/PRD.md#deployment) for deployment details.
