"""
Workflow state models for RFP Builder.
"""

from dataclasses import dataclass, field
from typing import Optional

from app.models.schemas import RFPAnalysis, RFPResponse, ProposalPlan, CritiqueResult, RFPRequirement


@dataclass
class DocumentInfo:
    """Information about an uploaded document."""
    filename: str
    file_type: str  # 'rfp', 'example', 'context'
    file_bytes: Optional[bytes] = None


@dataclass
class WorkflowInput:
    """Input data for the RFP workflow."""
    rfp_text: str
    rfp_images: Optional[list[dict]] = None  # For vision API
    example_rfps_text: list[str] = field(default_factory=list)
    example_rfps_images: Optional[list[list[dict]]] = None
    company_context_text: Optional[str] = None
    company_context_images: Optional[list[dict]] = None
    # Feature toggles (None = use config default)
    enable_planner: Optional[bool] = None
    enable_critiquer: Optional[bool] = None
    # Generator settings
    generator_formatting_injection: Optional[str] = None
    generator_intro_pages: Optional[int] = None
    generation_page_overlap: Optional[int] = None
    toggle_generation_chunking: Optional[bool] = None
    max_tokens_generation_chunking: Optional[int] = None
    max_sections_per_chunk: Optional[int] = None
    # Optional regeneration controls for step-by-step flows
    extract_reqs_comment: Optional[str] = None
    previous_requirements: Optional[list[RFPRequirement]] = None
    plan_comment: Optional[str] = None
    previous_plan: Optional[ProposalPlan] = None
    generate_rfp_comment: Optional[str] = None
    previous_document_code: Optional[str] = None
    critique_comment: Optional[str] = None
    # Document metadata for storing in run
    documents: list[DocumentInfo] = field(default_factory=list)


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
    run_id: Optional[str] = None  # The run directory name (e.g., "run_20260201_123456")
