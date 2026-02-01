"""
API Routes module.
"""

from .rfp import router as rfp_router
from .health import router as health_router
from .config import router as config_router

__all__ = ["rfp_router", "health_router", "config_router"]
