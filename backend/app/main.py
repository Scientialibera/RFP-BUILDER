"""
FastAPI Application Entry Point.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.core.config import get_config
from app.api import rfp_router, health_router, config_router, runs_router


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    config = get_config()
    
    # Create directories
    Path(config.app.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(config.app.output_dir).mkdir(parents=True, exist_ok=True)
    
    logger.info(f"RFP Builder v{__version__} starting...")
    logger.info(f"Using Azure: {config.use_azure}")
    logger.info(f"Auth enabled: {config.features.enable_auth}")
    logger.info(f"Images enabled: {config.features.enable_images}")
    
    yield
    
    logger.info("RFP Builder shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = get_config()
    
    cors_env = os.getenv("RFP_CORS_ALLOWED_ORIGINS", "")
    if cors_env.strip():
        cors_origins = [origin.strip() for origin in cors_env.split(",") if origin.strip()]
    else:
        cors_origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]
    
    app = FastAPI(
        title="RFP Builder API",
        description="Enterprise RFP generation powered by AI workflows",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health_router)
    app.include_router(config_router)
    app.include_router(rfp_router)
    app.include_router(runs_router)
    
    return app


# Application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    config = get_config()
    uvicorn.run(
        "app.main:app",
        host=config.app.host,
        port=config.app.port,
        reload=config.app.debug,
    )
