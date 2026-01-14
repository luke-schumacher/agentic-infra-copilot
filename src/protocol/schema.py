"""
Inter-Agent Communication Protocol - Schema Definitions

Defines the 'Agent Card' message format for standardized communication
between distributed agents in the Multi-Agent System.

Follows Telekom's 'External Minister' and 'Agent2Agent' patterns.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class AgentRole(str, Enum):
    """Enumeration of agent roles in the system."""
    TELEKOM_MINISTER = "telekom_minister"
    SIEMENS_TECHNICIAN = "siemens_technician"
    ILLIGO_OPERATOR = "illigo_operator"
    ORCHESTRATOR = "orchestrator"


class IntentType(str, Enum):
    """Types of intents agents can communicate."""
    QUERY = "query"                    # Request for information
    DIAGNOSE = "diagnose"              # Request for diagnosis
    VALIDATE = "validate"              # Request for validation
    REPORT = "report"                  # Status/results report
    DELEGATE = "delegate"              # Task delegation
    ESCALATE = "escalate"              # Priority escalation


class Priority(str, Enum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DocumentReference(BaseModel):
    """Reference to a retrieved document."""
    source: str
    file_name: str
    content_snippet: str = Field(max_length=500)
    relevance_score: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentCard(BaseModel):
    """
    Agent Card - Standard message format for inter-agent communication.

    This is the primary data structure for all communication between
    agents in the distributed MAS architecture.
    """
    # Message identification
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = Field(
        default=None,
        description="Links related messages in a conversation"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Routing information
    sender: AgentRole
    recipient: AgentRole

    # Intent and payload
    intent: IntentType
    priority: Priority = Priority.NORMAL

    # Main content
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Flexible payload containing query, context, or results"
    )

    # Evidence and citations
    documents: List[DocumentReference] = Field(default_factory=list)

    # Authentication/verification (future use)
    signature: Optional[str] = Field(
        default=None,
        description="Digital signature for message verification"
    )

    # Metadata for debugging and tracing
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "example": {
                "message_id": "abc123-def456",
                "sender": "orchestrator",
                "recipient": "telekom_minister",
                "intent": "query",
                "priority": "high",
                "payload": {
                    "query": "What is the SLA requirement for Koumassi microgrid?",
                    "context": {"location": "Koumassi", "domain": "latency"}
                },
                "documents": [],
                "signature": None
            }
        }
    }


class ConsultRequest(BaseModel):
    """Request model for the /consult endpoint."""
    card: AgentCard
    await_response: bool = Field(
        default=True,
        description="Whether to wait for synchronous response"
    )
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class ConsultResponse(BaseModel):
    """Response model from the /consult endpoint."""
    success: bool
    response_card: AgentCard
    processing_time_ms: float
    error: Optional[str] = None


class AgentHealthStatus(BaseModel):
    """Health check response for agent endpoints."""
    agent_role: AgentRole
    status: Literal["healthy", "degraded", "unhealthy"]
    vector_store_ready: bool
    dspy_ready: bool
    document_count: int
    last_query_time: Optional[datetime] = None
    uptime_seconds: float
