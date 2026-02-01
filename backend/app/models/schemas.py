"""
Pydantic schemas for API requests and responses.
"""

from typing import Optional
from pydantic import BaseModel, Field


# ============ RFP Section Models ============

class RFPSection(BaseModel):
    """A single section of an RFP response."""
    section_title: str = Field(..., description="Title of the section")
    section_content: str = Field(..., description="Content of the section (may include Mermaid)")
    section_type: str = Field(
        ..., 
        pattern="^(h1|h2|h3|body)$",
        description="Type: h1, h2, h3, or body"
    )


class RFPResponseMetadata(BaseModel):
    """Metadata about the generated RFP response."""
    total_sections: Optional[int] = None
    has_diagrams: Optional[bool] = None
    estimated_pages: Optional[int] = None


class RFPResponse(BaseModel):
    """Complete RFP response with sections."""
    sections: list[RFPSection]
    metadata: Optional[RFPResponseMetadata] = None


# ============ RFP Analysis Models ============

class RFPRequirement(BaseModel):
    """A requirement extracted from an RFP."""
    id: str = Field(..., description="Unique ID like REQ-001")
    description: str = Field(..., description="Requirement description")
    category: str = Field(
        ..., 
        pattern="^(technical|management|cost|experience|compliance|other)$"
    )
    is_mandatory: bool = Field(..., description="Whether mandatory")
    priority: Optional[str] = Field(
        None, 
        pattern="^(high|medium|low)$"
    )


class EvaluationCriterion(BaseModel):
    """An evaluation criterion from the RFP."""
    criterion: str
    weight: Optional[float] = None
    description: Optional[str] = None


class SubmissionRequirements(BaseModel):
    """Submission logistics from the RFP."""
    deadline: Optional[str] = None
    format: Optional[str] = None
    page_limit: Optional[int] = None
    sections_required: Optional[list[str]] = None


class RFPAnalysis(BaseModel):
    """Complete analysis of an RFP document."""
    summary: str = Field(..., description="Brief summary of the RFP")
    requirements: list[RFPRequirement]
    evaluation_criteria: Optional[list[EvaluationCriterion]] = None
    submission_requirements: Optional[SubmissionRequirements] = None
    key_differentiators: Optional[list[str]] = None


# ============ Review Models ============

class ReviewChange(BaseModel):
    """A required change from review."""
    section: str
    issue: str
    suggestion: str
    priority: Optional[str] = Field(
        None,
        pattern="^(critical|important|nice_to_have)$"
    )


class ReviewFeedback(BaseModel):
    """Review feedback on a proposal draft."""
    overall_score: int = Field(..., ge=1, le=10)
    compliance_status: str = Field(
        ...,
        pattern="^(compliant|partially_compliant|non_compliant)$"
    )
    strengths: Optional[list[str]] = None
    weaknesses: Optional[list[str]] = None
    required_changes: list[ReviewChange]
    missing_requirements: Optional[list[str]] = None


# ============ API Request/Response Models ============

class GenerateRFPRequest(BaseModel):
    """Request body for RFP generation (used with form data)."""
    # Note: Files are handled separately via UploadFile
    pass


class GenerateRFPResponse(BaseModel):
    """Response from RFP generation endpoint."""
    success: bool
    message: str
    rfp_response: Optional[RFPResponse] = None
    analysis: Optional[RFPAnalysis] = None
    pdf_download_url: Optional[str] = None
    processing_time_seconds: Optional[float] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    llm_configured: bool
    auth_enabled: bool
    images_enabled: bool


class ConfigResponse(BaseModel):
    """Public configuration response."""
    auth_enabled: bool
    images_enabled: bool
    msal_client_id: Optional[str] = None
    msal_tenant_id: Optional[str] = None
    msal_redirect_uri: Optional[str] = None
    msal_scopes: Optional[list[str]] = None
