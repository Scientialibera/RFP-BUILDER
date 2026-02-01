"""Prompts module - Contains all LLM prompts for the RFP Builder workflow."""

from .system_prompts import (
    RFP_ANALYZER_SYSTEM_PROMPT,
    RFP_SECTION_GENERATOR_SYSTEM_PROMPT,
)
from .user_prompts import (
    ANALYZE_RFP_USER_PROMPT,
    GENERATE_SECTIONS_USER_PROMPT,
)

__all__ = [
    "RFP_ANALYZER_SYSTEM_PROMPT",
    "RFP_SECTION_GENERATOR_SYSTEM_PROMPT",
    "ANALYZE_RFP_USER_PROMPT",
    "GENERATE_SECTIONS_USER_PROMPT",
]
