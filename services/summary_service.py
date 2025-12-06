"""
Summary Service using OpenAI GPT API.
Generates structured meeting summaries with overview, action items, and decisions.
"""
import os
import json
import re
import logging
from openai import OpenAI
from models.messages import SummaryBlock

logger = logging.getLogger(__name__)

# Lazy initialization of OpenAI client
_client = None


def _get_client() -> OpenAI:
    """Get or create OpenAI client instance."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        _client = OpenAI(api_key=api_key)
    return _client


async def generate_summary(
    full_transcript: str,
    language: str = None
) -> SummaryBlock:
    """
    Generate structured summary from full transcript using GPT API.
    
    Args:
        full_transcript: Complete meeting transcript text
        language: Source language code (optional, for prompt context)
    
    Returns:
        SummaryBlock with short_overview, action_items, and decisions
    
    Raises:
        Exception: If summary generation fails
    """
    import asyncio
    
    if not full_transcript or not full_transcript.strip():
        raise ValueError("Full transcript cannot be empty")
    
    try:
        # Build structured prompt
        lang_context = f" (in {language})" if language else ""
        prompt = f"""Analyze the following meeting transcript{lang_context} and provide a structured summary.

Transcript:
{full_transcript}

Please provide a JSON response with the following structure:
{{
    "short_overview": "A brief 2-5 sentence overview of the meeting",
    "action_items": ["Action item 1", "Action item 2", ...],
    "decisions": ["Decision 1", "Decision 2", ...]
}}

Return only valid JSON, no additional text."""
        
        # Call GPT API (run sync call in executor to avoid blocking)
        client = _get_client()
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional meeting assistant. Extract key information, action items, and decisions from meeting transcripts. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
        )
        
        # Parse JSON response
        response_text = response.choices[0].message.content.strip()
        
        # Try to parse as JSON
        try:
            summary_dict = json.loads(response_text)
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                summary_dict = json.loads(json_match.group(1))
            else:
                raise ValueError("Failed to parse summary response as JSON")
        
        # Validate and create SummaryBlock
        summary_block = SummaryBlock(
            short_overview=summary_dict.get("short_overview", ""),
            action_items=summary_dict.get("action_items", []),
            decisions=summary_dict.get("decisions", [])
        )
        
        return summary_block
    
    except Exception as e:
        logger.error(f"Summary generation failed: {str(e)}")
        raise

