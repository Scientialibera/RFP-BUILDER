"""
Configuration endpoints for frontend.
"""

from fastapi import APIRouter

from app.core.config import get_config
from app.models.schemas import ConfigResponse


router = APIRouter(prefix="/api/config", tags=["Config"])


@router.get("", response_model=ConfigResponse)
async def get_frontend_config():
    """
    Get frontend configuration.
    
    Returns public configuration needed by the frontend,
    including auth settings if enabled.
    """
    config = get_config()
    
    response = ConfigResponse(
        auth_enabled=config.features.enable_auth,
        images_enabled=config.features.enable_images,
    )
    
    # Only expose MSAL config if auth is enabled
    if config.features.enable_auth and config.msal.is_configured:
        response.msal_client_id = config.msal.client_id
        response.msal_tenant_id = config.msal.tenant_id
        response.msal_redirect_uri = config.msal.redirect_uri
        response.msal_scopes = config.msal.scopes
    
    return response
