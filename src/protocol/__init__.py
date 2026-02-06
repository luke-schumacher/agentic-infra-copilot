"""
Inter-Agent Communication Protocol

Defines standardized message formats for agent-to-agent communication
following the 'Agent2Agent' pattern.

Contains:
- schema.py: AgentCard, ConsultRequest/Response, enums

Author: Thesis Project - Agentic Infra Co-Pilot
"""

from .schema import (
    AgentRole,
    IntentType,
    ResponseType,
    Priority,
    DocumentReference,
    AgentCard,
    ConsultRequest,
    ConsultResponse,
    AgentHealthStatus,
)

__all__ = [
    "AgentRole",
    "IntentType",
    "ResponseType",
    "Priority",
    "DocumentReference",
    "AgentCard",
    "ConsultRequest",
    "ConsultResponse",
    "AgentHealthStatus",
]
