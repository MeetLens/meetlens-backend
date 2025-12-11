"""
Summary Service using LiteLLM for multi-provider support.
Generates structured meeting summaries with overview, action items, and decisions.
"""
import os
import json
import re
import logging
from litellm import RateLimitError, Timeout as APITimeoutError
from services.llm_service import complete_with_fallback
from models.messages import SummaryBlock

logger = logging.getLogger(__name__)

# Model can be overridden; default to a widely available, fast model
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "gpt-5-nano")


async def generate_summary(
    full_transcript: str,
    language: str = None
) -> SummaryBlock:
    """
    Generate structured summary from full transcript using LiteLLM.

    Args:
        full_transcript: Complete meeting transcript text
        language: Source language code (optional, for prompt context)

    Returns:
        SummaryBlock with short_overview, action_items, and decisions

    Raises:
        ValueError: If input transcript is empty
        Exception: If the LLM API returns an unrecoverable error
        Note: RateLimitError and APITimeoutError are handled gracefully with fallback
    """
    if not full_transcript or not full_transcript.strip():
        raise ValueError("Full transcript cannot be empty")

    # Prepare fallback summary
    fallback_summary = SummaryBlock(
        short_overview=full_transcript.strip(),
        action_items=[],
        decisions=[],
    )

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

        # Call LiteLLM with JSON response format
        # Note: Not all providers support response_format, LiteLLM will handle gracefully
        response_text = await complete_with_fallback(
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional meeting assistant. Extract key information, action items, and decisions from meeting transcripts. Always return valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            model=SUMMARY_MODEL,
            response_format={"type": "json_object"},
            request_name="summary",
            fallback_text=None,  # We'll handle fallback manually to return SummaryBlock
        )

        # Parse JSON response
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

    except (RateLimitError, APITimeoutError) as e:
        logger.warning(
            "Summary generation %s; returning transcript fallback: %s",
            "rate limited" if isinstance(e, RateLimitError) else "timed out",
            e
        )
        return fallback_summary
    except Exception as e:
        logger.error(f"Summary generation failed: {str(e)}")
        raise

