"""
API authentication utilities.
"""

import json
import logging
from typing import Optional
from fastapi import HTTPException, Header, Depends
from app.core.config import get_config

logger = logging.getLogger(__name__)


def _validate_token_fields(token: str, required_fields: list[dict[str, str]]) -> bool:
    """
    Validate token fields against required field/value pairs.
    
    Tokens are expected to be base64-encoded JSON strings.
    
    Args:
        token: The token string to validate (base64-encoded JSON)
        required_fields: List of dicts with 'field' and 'value' keys
        
    Returns:
        True if all required fields match their expected values
    """
    if not required_fields:
        return True
    
    import base64
    
    try:
        # Decode base64 token
        try:
            decoded = base64.b64decode(token, validate=True).decode('utf-8')
            token_data = json.loads(decoded)
        except (ValueError, json.JSONDecodeError) as e:
            logger.debug(f"Failed to decode/parse token: {str(e)}")
            return False
        
        # Check all required fields
        for field_spec in required_fields:
            field_name = field_spec.get("field")
            expected_value = field_spec.get("value")
            
            if not field_name or expected_value is None:
                logger.warning(f"Invalid field spec: {field_spec}")
                continue
            
            # Check if field exists and matches value
            actual_value = token_data.get(field_name)
            if actual_value != expected_value:
                logger.debug(f"Token field '{field_name}' mismatch: expected '{expected_value}', got '{actual_value}'")
                return False
        
        return True
        
    except Exception as e:
        logger.debug(f"Error validating token fields: {str(e)}")
        return False


async def verify_api_token(
    x_api_key: Optional[str] = Header(None)
) -> Optional[str]:
    """
    Verify API token from request header.
    
    Validates token against required field/value pairs.
    
    Args:
        x_api_key: API key from X-API-Key header (or configured header name)
        
    Returns:
        The API token if valid
        
    Raises:
        HTTPException: If auth is enabled and token is invalid
    """
    config = get_config()
    
    # If API auth is disabled, allow all requests
    if not config.api_auth.enabled:
        return None
    
    # Check if token is provided
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail=f"Missing API token. Provide token in {config.api_auth.header_name} header."
        )
    
    # Validate token fields
    if not _validate_token_fields(x_api_key, config.api_auth.required_fields):
        raise HTTPException(
            status_code=401,
            detail="Invalid API token. Required fields do not match."
        )
    
    return x_api_key


def require_api_token() -> Optional[str]:
    """Dependency for endpoints that require API authentication."""
    async def _verify(token: Optional[str] = Depends(verify_api_token)) -> Optional[str]:
        return token
    return Depends(_verify)
