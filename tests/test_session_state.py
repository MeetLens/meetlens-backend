"""
Unit tests for SessionState model and SessionManager.
Tests session lifecycle, state management, and thread-safety.
"""
import pytest
import asyncio
from models.messages import SessionState
from services.session_manager import SessionManager


class TestSessionState:
    """Test suite for SessionState model."""
    
    def test_initialization_with_defaults(self):
        """Test SessionState initialization with default values."""
        session_id = "test-session-1"
        state = SessionState(session_id=session_id)
        
        assert state.session_id == session_id
        assert state.last_stable_text == ""
        assert state.tail_words == []
        assert state.buffer_unstable == ""
        assert state.full_transcript == ""
    
    def test_initialization_with_custom_values(self):
        """Test SessionState initialization with custom values."""
        session_id = "test-session-2"
        state = SessionState(
            session_id=session_id,
            last_stable_text="Hello",
            tail_words=["hello"],
            buffer_unstable="world",
            full_transcript="Hello world"
        )
        
        assert state.session_id == session_id
        assert state.last_stable_text == "Hello"
        assert state.tail_words == ["hello"]
        assert state.buffer_unstable == "world"
        assert state.full_transcript == "Hello world"
    
    def test_state_mutation(self):
        """Test that SessionState fields can be mutated."""
        state = SessionState(session_id="test-session-3")
        
        state.last_stable_text = "New text"
        state.tail_words = ["new", "text"]
        state.buffer_unstable = "partial"
        state.full_transcript = "New text partial"
        
        assert state.last_stable_text == "New text"
        assert state.tail_words == ["new", "text"]
        assert state.buffer_unstable == "partial"
        assert state.full_transcript == "New text partial"


class TestSessionManager:
    """Test suite for SessionManager."""
    
    @pytest.mark.asyncio
    async def test_get_or_create_creates_new_session(self):
        """Test that get_or_create creates a new session when it doesn't exist."""
        manager = SessionManager()
        session_id = "new-session-1"
        
        state = await manager.get_or_create(session_id)
        
        assert state is not None
        assert state.session_id == session_id
        assert state.last_stable_text == ""
        assert state.tail_words == []
        assert state.buffer_unstable == ""
        assert state.full_transcript == ""
    
    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing_session(self):
        """Test that get_or_create returns existing session."""
        manager = SessionManager()
        session_id = "existing-session-1"
        
        # Create session
        state1 = await manager.get_or_create(session_id)
        state1.last_stable_text = "Modified"
        
        # Get same session
        state2 = await manager.get_or_create(session_id)
        
        assert state2 is state1  # Should be same object
        assert state2.last_stable_text == "Modified"
    
    @pytest.mark.asyncio
    async def test_get_returns_existing_session(self):
        """Test that get returns existing session."""
        manager = SessionManager()
        session_id = "get-session-1"
        
        # Create session
        created_state = await manager.get_or_create(session_id)
        created_state.last_stable_text = "Test"
        
        # Get session
        retrieved_state = await manager.get(session_id)
        
        assert retrieved_state is not None
        assert retrieved_state.session_id == session_id
        assert retrieved_state.last_stable_text == "Test"
    
    @pytest.mark.asyncio
    async def test_get_returns_none_for_nonexistent_session(self):
        """Test that get returns None for non-existent session."""
        manager = SessionManager()
        session_id = "nonexistent-session-1"
        
        state = await manager.get(session_id)
        
        assert state is None
    
    @pytest.mark.asyncio
    async def test_update_modifies_state(self):
        """Test that update modifies session state."""
        manager = SessionManager()
        session_id = "update-session-1"
        
        # Create session
        state = await manager.get_or_create(session_id)
        state.last_stable_text = "Original"
        
        # Update state
        state.last_stable_text = "Updated"
        await manager.update(session_id, state)
        
        # Retrieve and verify
        retrieved_state = await manager.get(session_id)
        assert retrieved_state is not None
        assert retrieved_state.last_stable_text == "Updated"
    
    @pytest.mark.asyncio
    async def test_finalize_returns_session_state(self):
        """Test that finalize returns session state."""
        manager = SessionManager()
        session_id = "finalize-session-1"
        
        # Create and modify session
        state = await manager.get_or_create(session_id)
        state.full_transcript = "Complete transcript"
        
        # Finalize
        finalized_state = await manager.finalize(session_id)
        
        assert finalized_state is not None
        assert finalized_state.session_id == session_id
        assert finalized_state.full_transcript == "Complete transcript"
    
    @pytest.mark.asyncio
    async def test_finalize_returns_none_for_nonexistent_session(self):
        """Test that finalize returns None for non-existent session."""
        manager = SessionManager()
        session_id = "nonexistent-finalize-1"
        
        finalized_state = await manager.finalize(session_id)
        
        assert finalized_state is None
    
    @pytest.mark.asyncio
    async def test_multiple_sessions_independent(self):
        """Test that multiple sessions are independent."""
        manager = SessionManager()
        session_id_1 = "multi-session-1"
        session_id_2 = "multi-session-2"
        
        # Create two sessions
        state1 = await manager.get_or_create(session_id_1)
        state2 = await manager.get_or_create(session_id_2)
        
        # Modify one
        state1.last_stable_text = "Session 1"
        state2.last_stable_text = "Session 2"
        
        # Verify independence
        retrieved1 = await manager.get(session_id_1)
        retrieved2 = await manager.get(session_id_2)
        
        assert retrieved1.last_stable_text == "Session 1"
        assert retrieved2.last_stable_text == "Session 2"
        assert retrieved1 is not retrieved2
    
    @pytest.mark.asyncio
    async def test_thread_safety_concurrent_get_or_create(self):
        """Test thread-safety with concurrent get_or_create calls."""
        manager = SessionManager()
        session_id = "concurrent-session-1"
        
        # Create multiple concurrent tasks
        async def create_session():
            return await manager.get_or_create(session_id)
        
        tasks = [create_session() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All should return the same session object
        first_result = results[0]
        for result in results:
            assert result is first_result
            assert result.session_id == session_id
    
    @pytest.mark.asyncio
    async def test_thread_safety_concurrent_updates(self):
        """Test thread-safety with concurrent update calls."""
        manager = SessionManager()
        session_id = "concurrent-update-1"
        
        # Create session
        state = await manager.get_or_create(session_id)
        
        # Concurrent updates
        async def update_session(value):
            state = await manager.get(session_id)
            state.last_stable_text = value
            await manager.update(session_id, state)
        
        tasks = [update_session(f"Update {i}") for i in range(5)]
        await asyncio.gather(*tasks)
        
        # Final state should be one of the updates (last one wins due to lock)
        retrieved = await manager.get(session_id)
        assert retrieved is not None
        assert "Update" in retrieved.last_stable_text
    
    @pytest.mark.asyncio
    async def test_cleanup_old_sessions_no_error(self):
        """Test that cleanup_old_sessions doesn't raise errors (MVP implementation)."""
        manager = SessionManager()
        session_id = "cleanup-session-1"
        
        # Create session
        await manager.get_or_create(session_id)
        
        # Cleanup should not raise
        await manager.cleanup_old_sessions(max_age_seconds=3600)
        
        # Session should still exist (MVP doesn't actually clean up)
        state = await manager.get(session_id)
        assert state is not None

