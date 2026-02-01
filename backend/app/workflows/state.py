"""
Workflow state models for RFP Builder.
"""

from dataclasses import dataclass, field
from typing import Optional

from app.models.schemas import RFPAnalysis, RFPResponse, ProposalPlan, CritiqueResult


@dataclass
class WorkflowInput:
    """Input data for the RFP workflow."""
    rfp_text: str
    rfp_images: Optional[list[dict]] = None  # For vision API
    example_rfps_text: list[str] = field(default_factory=list)
    example_rfps_images: Optional[list[list[dict]]] = None
    company_context_text: Optional[str] = None
    company_context_images: Optional[list[dict]] = None
    generator_formatting_injection: Optional[str] = None
    generator_intro_pages: Optional[int] = None
    generation_page_overlap: Optional[int] = None
    toggle_generation_chunking: Optional[bool] = None
    max_tokens_generation_chunking: Optional[int] = None
    max_sections_per_chunk: Optional[int] = None


@dataclass
class AnalysisResult:
    """Result from the analyzer executor."""
    analysis: RFPAnalysis
    raw_response: str


@dataclass
class PlanningResult:
    """Result from the planner executor."""
    plan: ProposalPlan
    raw_response: str


@dataclass
class GenerationResult:
    """Result from the section generator executor."""
    response: RFPResponse
    raw_response: str


@dataclass
class CritiqueResultData:
    """Result from the critiquer executor."""
    critique: CritiqueResult
    raw_response: str


@dataclass
class FinalResult:
    """Final result from the workflow."""
    response: RFPResponse
    analysis: RFPAnalysis
    plan: Optional[ProposalPlan] = None
    critique_history: list[CritiqueResult] = field(default_factory=list)
    error_recovery_count: int = 0
    docx_path: Optional[str] = None
    execution_stats: Optional[dict] = None
