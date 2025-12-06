"""
TranscriptMerger handles deduplication and stabilization of transcript segments.
Implements overlap detection and sentence boundary detection as per Architecture & Flow spec.
"""
import re
import logging
from typing import Tuple, Optional, List
from models.messages import SessionState

logger = logging.getLogger(__name__)

# Number of tail words to keep for overlap detection
TAIL_WORDS_COUNT = 10


def process_transcript(
    raw_text: str,
    session_state: SessionState
) -> Tuple[Optional[str], Optional[str]]:
    """
    Process new transcript chunk and merge with existing state.
    
    Args:
        raw_text: New transcript text from Whisper
        session_state: Current session state
    
    Returns:
        Tuple of (partial_text, stable_segment)
        - partial_text: Unstable/partial text to show immediately (optional)
        - stable_segment: Stable completed segment (optional)
    """
    if not raw_text or not raw_text.strip():
        return None, None
    
    # Clean and normalize the raw text (preserve case)
    raw_text = raw_text.strip()
    
    # Get tail words from last stable text (for overlap detection, use lowercase)
    tail_words = session_state.tail_words.copy()
    
    # Split raw text into words (preserving punctuation, lowercase for comparison)
    raw_words_lower = _tokenize_text_lower(raw_text)
    raw_words_original = _tokenize_text_preserve_case(raw_text)
    
    if not raw_words_lower:
        return None, None
    
    # Find overlap between tail_words and beginning of raw_words (using lowercase)
    overlap_length = _find_overlap(tail_words, raw_words_lower)
    
    # Remove overlapping portion from raw_words
    if overlap_length > 0:
        new_words_original = raw_words_original[overlap_length:]
    else:
        new_words_original = raw_words_original
    
    if not new_words_original:
        # All words were duplicates, return partial only
        partial_text = raw_text
        return partial_text, None
    
    # Build new text from unique words (preserving original case)
    new_text = " ".join(new_words_original)
    
    # Update buffer_unstable with new text
    if session_state.buffer_unstable:
        session_state.buffer_unstable += " " + new_text
    else:
        session_state.buffer_unstable = new_text
    
    # Check for sentence boundaries (preserve punctuation)
    stable_segment = None
    partial_text = session_state.buffer_unstable
    
    # Find sentence endings while preserving punctuation
    # Match text ending with . ! or ? followed by optional whitespace
    sentence_end_pattern = r'([^.!?]*[.!?])\s*'
    matches = list(re.finditer(sentence_end_pattern, session_state.buffer_unstable))
    
    # If we found complete sentences
    if matches:
        # Get the last match to find where complete sentences end
        last_match = matches[-1]
        end_pos = last_match.end()
        
        # Extract stable segment (all complete sentences)
        stable_segment = session_state.buffer_unstable[:end_pos].strip()
        
        # Remaining text after the last sentence ending
        remaining_text = session_state.buffer_unstable[end_pos:].strip()
        
        # Update state
        session_state.full_transcript += " " + stable_segment if session_state.full_transcript else stable_segment
        session_state.last_stable_text = stable_segment
        
        # Update tail_words from stable segment (lowercase for overlap detection)
        stable_words_lower = _tokenize_text_lower(stable_segment)
        session_state.tail_words = stable_words_lower[-TAIL_WORDS_COUNT:] if len(stable_words_lower) >= TAIL_WORDS_COUNT else stable_words_lower
        
        # Keep only the remaining incomplete text in buffer
        session_state.buffer_unstable = remaining_text
        partial_text = session_state.buffer_unstable
    
    return partial_text, stable_segment


def _tokenize_text_lower(text: str) -> List[str]:
    """
    Tokenize text into words (lowercase) for overlap detection.
    """
    words = re.findall(r'\S+', text.lower())
    return words


def _tokenize_text_preserve_case(text: str) -> List[str]:
    """
    Tokenize text into words, preserving case and punctuation.
    """
    words = re.findall(r'\S+', text)
    return words


def _find_overlap(tail_words: List[str], new_words: List[str]) -> int:
    """
    Find the longest overlap between tail_words and the beginning of new_words.
    
    Returns:
        Length of overlap (number of matching words from the start)
    """
    if not tail_words or not new_words:
        return 0
    
    max_overlap = min(len(tail_words), len(new_words))
    
    # Try different overlap lengths, starting from the longest possible
    for overlap_len in range(max_overlap, 0, -1):
        tail_slice = tail_words[-overlap_len:]
        new_slice = new_words[:overlap_len]
        
        if tail_slice == new_slice:
            return overlap_len
    
    return 0

