"""
Pydantic schemas for API requests and responses.

Simplified structure:
- RFPResponse has ONE document_code field
- The LLM writes complete python-docx code with seaborn charts and mermaid diagrams inline
"""

from typing import Optional
from pydantic import BaseModel, Field


# ============ RFP Response Model ============

class RFPResponse(BaseModel):
    """
    Complete RFP response.
    
    The document_code field contains Python code that creates the full Word document.
    The code can use python-docx, seaborn/matplotlib for charts, and mermaid CLI for diagrams.
    """
    document_code: str = Field(
        ..., 
        description="Python code that creates the complete proposal Word document."
    )


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


# ============ API Request/Response Models ============

class GenerateRFPRequest(BaseModel):
    """Request body for RFP generation (used with form data)."""
    pass


class GenerateRFPResponse(BaseModel):
    """Response from RFP generation endpoint."""
    success: bool
    message: str
    rfp_response: Optional[RFPResponse] = None
    analysis: Optional[RFPAnalysis] = None
    docx_download_url: Optional[str] = None
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
