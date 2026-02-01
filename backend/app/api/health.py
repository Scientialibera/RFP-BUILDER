"""
Health check endpoints.
"""

from fastapi import APIRouter

from app import __version__
from app.core.config import get_config
from app.models.schemas import HealthResponse


router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns service status and configuration information.
    """
    config = get_config()
    
    return HealthResponse(
        status="healthy",
        version=__version__,
        llm_configured=config.use_azure or config.openai.is_configured,
        auth_enabled=config.features.enable_auth,
        images_enabled=config.features.enable_images,
    )


@router.get("/")
async def root():
    """Root endpoint - redirects to docs."""
    return {
        "message": "RFP Builder API",
        "docs": "/docs",
        "health": "/health"
    }
