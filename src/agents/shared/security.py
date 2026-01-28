"""
Security Configuration - Shared CORS and Security Settings

Provides secure CORS configuration with environment-based origin control.
Default origins allow Streamlit UI on localhost for development.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import os
import logging
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


def get_allowed_origins() -> List[str]:
    """
    Get allowed CORS origins from environment or defaults.

    Environment variable: CORS_ALLOWED_ORIGINS (comma-separated)
    Default (development): localhost origins for Streamlit UI

    Returns:
        List of allowed origin URLs
    """
    env_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")

    if env_origins:
        origins = [origin.strip() for origin in env_origins.split(",") if origin.strip()]
        logger.info(f"Using CORS origins from environment: {origins}")
        return origins

    # Development defaults - Streamlit UI on common localhost ports
    default_origins = [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    logger.debug(f"Using default CORS origins: {default_origins}")
    return default_origins


def configure_cors(app: FastAPI, allow_credentials: bool = True) -> None:
    """
    Configure CORS middleware with secure defaults.

    Restricts allowed origins to known clients (Streamlit UI by default).
    Can be configured via CORS_ALLOWED_ORIGINS environment variable.

    Args:
        app: FastAPI application instance
        allow_credentials: Whether to allow credentials (default: True)

    Example:
        app = FastAPI()
        configure_cors(app)
    """
    allowed_origins = get_allowed_origins()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST"],  # Restrict to needed methods
        allow_headers=["Content-Type", "Authorization"],
    )

    logger.info(f"CORS configured with {len(allowed_origins)} allowed origins")
