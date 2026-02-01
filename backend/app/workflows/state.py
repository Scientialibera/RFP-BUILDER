"""
Workflow state models for RFP Builder.
"""

from dataclasses import dataclass, field
from typing import Optional

from app.models.schemas import RFPAnalysis, RFPResponse, ReviewFeedback


@dataclass
class WorkflowInput:
    """Input data for the RFP workflow."""
    rfp_text: str
    rfp_images: Optional[list[dict]] = None  # For vision API
    example_rfps_text: list[str] = field(default_factory=list)
    example_rfps_images: Optional[list[list[dict]]] = None
    company_context_text: Optional[str] = None
    company_context_images: Optional[list[dict]] = None


@dataclass
class AnalysisResult:
    """Result from the analyzer executor."""
    analysis: RFPAnalysis
    raw_response: str


@dataclass
class GenerationResult:
    """Result from the section generator executor."""
    response: RFPResponse
    raw_response: str


@dataclass
class ReviewResult:
    """Result from the reviewer executor."""
    feedback: ReviewFeedback
    raw_response: str


@dataclass
class FinalResult:
    """Final result from the workflow."""
    response: RFPResponse
    analysis: RFPAnalysis
    review: Optional[ReviewFeedback] = None
