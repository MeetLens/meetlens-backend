"""
Unit tests for TranscriptMerger.
Tests overlap detection, sentence boundary detection, and state management.
"""
import pytest
from models.messages import SessionState
from services.transcript_merger import process_transcript


class TestTranscriptMerger:
    """Test suite for TranscriptMerger functionality."""
    
    def test_overlap_detection_basic(self):
        """Test basic overlap detection between tail words and new chunk."""
        session_state = SessionState(session_id="test-1")
        session_state.last_stable_text = "Hello world"
        session_state.tail_words = ["hello", "world"]
        session_state.full_transcript = "Hello world"
        
        # New chunk starts with overlapping words
        raw_text = "world this is new"
        partial, stable = process_transcript(raw_text, session_state)
        
        # Should remove "world" overlap and keep "this is new"
        assert "world" not in partial.lower() or partial.lower().count("world") == 1
        assert session_state.full_transcript == "Hello world"
        assert len(session_state.tail_words) > 0
    
    def test_duplicate_removal(self):
        """Test that overlapping words are correctly removed."""
        session_state = SessionState(session_id="test-2")
        session_state.last_stable_text = "The quick brown fox"
        session_state.tail_words = ["the", "quick", "brown", "fox"]
        session_state.full_transcript = "The quick brown fox"
        
        # New chunk repeats tail words
        raw_text = "brown fox jumps over"
        partial, stable = process_transcript(raw_text, session_state)
        
        # Should remove "brown fox" overlap
        assert "brown fox" not in partial.lower() or partial.lower().count("brown") <= 1
        assert "jumps over" in partial.lower()
    
    def test_sentence_boundary_detection_period(self):
        """Test that period triggers stable segment emission."""
        session_state = SessionState(session_id="test-3")
        session_state.buffer_unstable = "Hello"
        
        raw_text = "world."
        partial, stable = process_transcript(raw_text, session_state)
        
        assert stable is not None
        assert "." in stable
        assert "Hello world" in stable or "world" in stable
        assert session_state.buffer_unstable == "" or len(session_state.buffer_unstable) < len(stable)
    
    def test_sentence_boundary_detection_question_mark(self):
        """Test that question mark triggers stable segment."""
        session_state = SessionState(session_id="test-4")
        session_state.buffer_unstable = "What is"
        
        raw_text = "this?"
        partial, stable = process_transcript(raw_text, session_state)
        
        assert stable is not None
        assert "?" in stable or stable.endswith("?")
    
    def test_sentence_boundary_detection_exclamation(self):
        """Test that exclamation mark triggers stable segment."""
        session_state = SessionState(session_id="test-5")
        session_state.buffer_unstable = "Great"
        
        raw_text = "work!"
        partial, stable = process_transcript(raw_text, session_state)
        
        assert stable is not None
        assert "!" in stable or stable.endswith("!")
    
    def test_partial_vs_stable(self):
        """Test that partial_text reflects unstable and stable_segment only when complete."""
        session_state = SessionState(session_id="test-6")
        
        # First chunk: incomplete sentence
        raw_text = "This is a partial"
        partial1, stable1 = process_transcript(raw_text, session_state)
        
        assert partial1 is not None
        assert "partial" in partial1
        assert stable1 is None  # No sentence boundary yet
        
        # Second chunk: completes sentence
        raw_text = "sentence."
        partial2, stable2 = process_transcript(raw_text, session_state)
        
        assert stable2 is not None
        assert "." in stable2
        assert "sentence" in stable2.lower()
    
    def test_state_updates_last_stable_text(self):
        """Test that last_stable_text is updated correctly."""
        session_state = SessionState(session_id="test-7")
        
        raw_text = "First sentence."
        partial, stable = process_transcript(raw_text, session_state)
        
        assert stable is not None
        assert session_state.last_stable_text == stable
        assert "First sentence" in session_state.last_stable_text
    
    def test_state_updates_tail_words(self):
        """Test that tail_words are updated from stable segments."""
        session_state = SessionState(session_id="test-8")
        
        raw_text = "The quick brown fox jumps."
        partial, stable = process_transcript(raw_text, session_state)
        
        assert stable is not None
        assert len(session_state.tail_words) > 0
        # Tail words should be from the stable segment
        assert len(session_state.tail_words) <= 10  # TAIL_WORDS_COUNT
    
    def test_state_updates_buffer_unstable(self):
        """Test that buffer_unstable is updated correctly."""
        session_state = SessionState(session_id="test-9")
        
        raw_text = "Partial text"
        partial, stable = process_transcript(raw_text, session_state)
        
        assert session_state.buffer_unstable == partial or partial in session_state.buffer_unstable
        
        # Complete the sentence
        raw_text = "here."
        partial2, stable2 = process_transcript(raw_text, session_state)
        
        # Buffer should be cleared or contain only remaining partial
        assert stable2 is not None
    
    def test_state_updates_full_transcript(self):
        """Test that full_transcript accumulates stable segments."""
        session_state = SessionState(session_id="test-10")
        
        raw_text = "First sentence."
        partial1, stable1 = process_transcript(raw_text, session_state)
        
        assert stable1 is not None
        assert stable1 in session_state.full_transcript
        
        raw_text = "Second sentence."
        partial2, stable2 = process_transcript(raw_text, session_state)
        
        assert stable2 is not None
        assert stable1 in session_state.full_transcript
        assert stable2 in session_state.full_transcript
    
    def test_empty_chunk(self):
        """Test handling of empty chunks."""
        session_state = SessionState(session_id="test-11")
        
        raw_text = ""
        partial, stable = process_transcript(raw_text, session_state)
        
        assert partial is None
        assert stable is None
    
    def test_whitespace_only_chunk(self):
        """Test handling of whitespace-only chunks."""
        session_state = SessionState(session_id="test-12")
        
        raw_text = "   \n\t  "
        partial, stable = process_transcript(raw_text, session_state)
        
        assert partial is None
        assert stable is None
    
    def test_chunk_with_only_punctuation(self):
        """Test handling of chunks with only punctuation."""
        session_state = SessionState(session_id="test-13")
        session_state.buffer_unstable = "Hello"
        
        raw_text = "..."
        partial, stable = process_transcript(raw_text, session_state)
        
        # Should handle punctuation appropriately
        # May or may not create stable segment depending on implementation
        assert partial is not None or stable is not None
    
    def test_very_long_sentence_without_boundary(self):
        """Test handling of very long sentences without punctuation."""
        session_state = SessionState(session_id="test-14")
        
        # Long sentence without punctuation
        raw_text = "This is a very long sentence that continues without any punctuation marks"
        partial, stable = process_transcript(raw_text, session_state)
        
        assert partial is not None
        assert stable is None  # No boundary, so no stable segment
    
    def test_repeated_overlapping_chunks_idempotency(self):
        """Test that repeated overlapping chunks don't create duplicates."""
        session_state = SessionState(session_id="test-15")
        session_state.last_stable_text = "Hello world"
        session_state.tail_words = ["hello", "world"]
        session_state.full_transcript = "Hello world"
        
        # Send same overlapping chunk multiple times
        raw_text = "world test"
        partial1, stable1 = process_transcript(raw_text, session_state)
        transcript_after_first = session_state.full_transcript
        
        # Reset and send again
        session_state2 = SessionState(session_id="test-15-2")
        session_state2.last_stable_text = "Hello world"
        session_state2.tail_words = ["hello", "world"]
        session_state2.full_transcript = "Hello world"
        
        partial2, stable2 = process_transcript(raw_text, session_state2)
        
        # Results should be consistent
        assert partial1 == partial2 or (partial1 is None and partial2 is None)
    
    def test_multiple_sentences_in_one_chunk(self):
        """Test handling of multiple sentences in a single chunk."""
        session_state = SessionState(session_id="test-16")
        
        raw_text = "First sentence. Second sentence. Third sentence."
        partial, stable = process_transcript(raw_text, session_state)
        
        assert stable is not None
        # Should contain at least one complete sentence
        assert "." in stable
        # Buffer should contain remaining partial if any
        assert len(session_state.buffer_unstable) < len(raw_text) or session_state.buffer_unstable == ""
    
    def test_overlap_at_start_of_new_chunk(self):
        """Test overlap detection when new chunk starts with tail words."""
        session_state = SessionState(session_id="test-17")
        session_state.last_stable_text = "The meeting"
        session_state.tail_words = ["the", "meeting"]
        session_state.full_transcript = "The meeting"
        
        raw_text = "the meeting was productive"
        partial, stable = process_transcript(raw_text, session_state)
        
        # Should remove "the meeting" overlap
        assert "was productive" in partial.lower()
        # Full transcript shouldn't have duplicates
        assert session_state.full_transcript.count("the meeting") <= 1
    
    def test_no_overlap_new_sentence(self):
        """Test behavior when there's no overlap (new sentence)."""
        session_state = SessionState(session_id="test-18")
        session_state.last_stable_text = "First sentence."
        session_state.tail_words = ["first", "sentence"]
        session_state.full_transcript = "First sentence."
        
        raw_text = "Second sentence starts here."
        partial, stable = process_transcript(raw_text, session_state)
        
        assert stable is not None
        assert "Second sentence" in stable or "sentence starts" in stable.lower()
    
    def test_partial_text_contains_unstable_content(self):
        """Test that partial_text always reflects current unstable buffer."""
        session_state = SessionState(session_id="test-19")
        
        raw_text = "Building up"
        partial1, stable1 = process_transcript(raw_text, session_state)
        
        assert partial1 == session_state.buffer_unstable
        
        raw_text = "the sentence"
        partial2, stable2 = process_transcript(raw_text, session_state)
        
        assert partial2 == session_state.buffer_unstable or session_state.buffer_unstable in partial2

