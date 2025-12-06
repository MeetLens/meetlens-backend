"""
Session Manager for maintaining per-session state.
Uses in-memory storage for MVP (can be replaced with Redis later).
"""
import asyncio
from typing import Dict, Optional
from models.messages import SessionState


class SessionManager:
    """Thread-safe in-memory session state manager."""
    
    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._lock = asyncio.Lock()
    
    async def get_or_create(self, session_id: str) -> SessionState:
        """
        Get existing session state or create a new one.
        Thread-safe operation.
        """
        async with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionState(session_id=session_id)
            return self._sessions[session_id]
    
    async def get(self, session_id: str) -> Optional[SessionState]:
        """Get session state if it exists, None otherwise."""
        async with self._lock:
            return self._sessions.get(session_id)
    
    async def update(self, session_id: str, state: SessionState) -> None:
        """Update session state."""
        async with self._lock:
            self._sessions[session_id] = state
    
    async def finalize(self, session_id: str) -> Optional[SessionState]:
        """Finalize session (mark as ended, but keep state for summary)."""
        async with self._lock:
            return self._sessions.get(session_id)
    
    async def cleanup_old_sessions(self, max_age_seconds: int = 3600) -> None:
        """Clean up old sessions (optional, for future use)."""
        # MVP: Simple implementation - can be enhanced later
        pass


# Global session manager instance
session_manager = SessionManager()

