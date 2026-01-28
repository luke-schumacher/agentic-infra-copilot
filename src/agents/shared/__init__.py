"""
Shared utilities for all agents in the MAS architecture.

Contains:
- dspy_config.py: DSPy configuration with Groq LLM
- graph_service.py: Knowledge Graph access for hybrid search
- server_utils.py: Port management and server startup utilities
- security.py: CORS and security configuration
- embeddings.py: Shared embedding configuration (future)

Author: Thesis Project - Agentic Infra Co-Pilot
"""

from src.agents.shared.graph_service import GraphService, get_graph_service
from src.agents.shared.server_utils import (
    find_available_port,
    run_agent_server,
    is_port_available,
    PortNotAvailableError
)
from src.agents.shared.security import (
    configure_cors,
    get_allowed_origins
)

__all__ = [
    'GraphService',
    'get_graph_service',
    'find_available_port',
    'run_agent_server',
    'is_port_available',
    'PortNotAvailableError',
    'configure_cors',
    'get_allowed_origins'
]
