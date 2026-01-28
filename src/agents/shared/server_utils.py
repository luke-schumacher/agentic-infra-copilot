"""
Server Utilities - Shared Port Management for All Agents

Provides utilities for port discovery and server startup with automatic
port fallback when the preferred port is unavailable.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import socket
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class PortNotAvailableError(Exception):
    """Raised when no available port can be found after max attempts."""
    pass


def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """
    Check if a port is available for binding.

    Args:
        port: Port number to check
        host: Host address to bind to

    Returns:
        True if port is available, False otherwise
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            return True
    except OSError:
        return False


def find_available_port(
    preferred_port: int,
    max_attempts: int = 10,
    host: str = "0.0.0.0"
) -> int:
    """
    Find an available port, starting with the preferred port.

    If the preferred port is taken, increments and tries subsequent ports
    up to max_attempts times.

    Args:
        preferred_port: The port to try first
        max_attempts: Maximum number of ports to try (default: 10)
        host: Host address to bind to (default: "0.0.0.0")

    Returns:
        An available port number

    Raises:
        PortNotAvailableError: If no available port found within max_attempts
    """
    for attempt in range(max_attempts):
        port = preferred_port + attempt
        if is_port_available(port, host):
            if attempt > 0:
                logger.warning(
                    f"Preferred port {preferred_port} unavailable. "
                    f"Using port {port} instead."
                )
            return port
        logger.debug(f"Port {port} is not available, trying next...")

    raise PortNotAvailableError(
        f"Could not find an available port after {max_attempts} attempts "
        f"starting from port {preferred_port}"
    )


def run_agent_server(
    app,
    agent_name: str,
    env_var_name: str,
    default_port: int,
    max_port_attempts: int = 10,
    host: str = "0.0.0.0"
) -> None:
    """
    Run an agent FastAPI server with automatic port discovery.

    This function handles the common pattern of starting a uvicorn server
    with fallback port selection if the preferred port is unavailable.

    Args:
        app: FastAPI application instance
        agent_name: Human-readable agent name for logging
        env_var_name: Environment variable name for port configuration
        default_port: Default port if env var not set
        max_port_attempts: Max ports to try if preferred is taken (default: 10)
        host: Host address to bind to (default: "0.0.0.0")

    Example:
        run_agent_server(
            app=app,
            agent_name="Telekom Minister",
            env_var_name="TELEKOM_MINISTER_PORT",
            default_port=8001
        )
    """
    import uvicorn

    preferred_port = int(os.getenv(env_var_name, str(default_port)))

    try:
        actual_port = find_available_port(preferred_port, max_port_attempts, host)

        logger.info(f"Starting {agent_name} on port {actual_port}...")

        # Store actual port in app state for reference by health checks
        app.state.actual_port = actual_port

        uvicorn.run(
            app,
            host=host,
            port=actual_port,
            log_level="info"
        )
    except PortNotAvailableError as e:
        logger.error(f"Failed to start {agent_name}: {e}")
        raise SystemExit(1)
