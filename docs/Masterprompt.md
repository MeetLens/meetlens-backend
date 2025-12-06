You are cooperating inside a multi-agent environment to build the MeetLens MVP.

Project structure:
- /docs  → contains full specifications (Architecture & Flow, API & Schema Contract, Product Positioning, MVP Acceptance Criteria).
- /backend → FastAPI backend
- /frontend → Flutter mobile app

You MUST strictly follow all requirements defined in:
/docs/Architecture & Flow (MVP).md
/docs/API & Schema Contract.md
/docs/MVP Acceptance Criteria.md
/docs/MeetLens Product Positioning.md

Key high-level rules (do not violate):
- Real-time audio → 2s chunking → WebSocket `/ws/transcribe`
- Client receives: transcript_partial, transcript_stable, translation
- Summary generated via POST /summary
- SessionState + TranscriptMerger must follow spec exactly
- MVP only: NO authentication, NO pricing, NO diarization, NO calendar system

When generating code, preserve directory boundaries:
- All backend code goes into /backend
- All frontend (Flutter) code goes into /frontend

Be concise, deterministic, and avoid adding out-of-scope features.
