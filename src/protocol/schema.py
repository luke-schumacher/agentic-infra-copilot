"""
Inter-Agent Communication Protocol - Schema Definitions

Defines the 'Agent Card' message format for standardized communication
between distributed agents in the Multi-Agent System.

Follows Telekom's 'External Minister' and 'Agent2Agent' patterns.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Set
from enum import Enum
from pydantic import BaseModel, Field, field_serializer
import uuid


class AgentRole(str, Enum):
    """Enumeration of agent roles in the system."""
    # New role names (primary)
    GOVERNANCE_AGENT = "governance_agent"
    HARDWARE_AGENT = "hardware_agent"
    TELEMETRY_AGENT = "telemetry_agent"
    ORCHESTRATOR = "orchestrator"
    # Legacy aliases (deprecated - kept for backwards compatibility)
    TELEKOM_MINISTER = "governance_agent"
    SIEMENS_TECHNICIAN = "hardware_agent"
    ILLIGO_OPERATOR = "telemetry_agent"


class IntentType(str, Enum):
    """Types of intents agents can communicate."""
    QUERY = "query"                    # Request for information
    DIAGNOSE = "diagnose"              # Request for diagnosis
    VALIDATE = "validate"              # Request for validation
    REPORT = "report"                  # Status/results report
    DELEGATE = "delegate"              # Task delegation
    ESCALATE = "escalate"              # Priority escalation


class ResponseType(str, Enum):
    """Types of responses agents can provide for autonomy protocol."""
    ANSWER = "answer"           # Complete, confident answer
    PARTIAL = "partial"         # Partial answer, needs more context
    CLARIFY = "clarify"         # Needs clarification from requester
    REDIRECT = "redirect"       # Should be handled by different agent
    REFUSE = "refuse"           # Cannot or should not answer
    CONSULT = "consult"         # Answered after consulting another agent


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

    # Autonomy protocol fields (new)
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Agent's confidence in its response (0.0-1.0)"
    )
    response_type: ResponseType = Field(
        default=ResponseType.ANSWER,
        description="Type of response being provided"
    )
    suggested_agent: Optional[AgentRole] = Field(
        default=None,
        description="Suggested agent for REDIRECT/CONSULT response types"
    )

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

    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime) -> str:
        """Serialize datetime to ISO format string for JSON compatibility."""
        return value.isoformat() if value else None


class AgentResponse(BaseModel):
    """
    Structured response from an agent following the autonomy protocol.

    This schema enables agents to express their capability and reasoning
    when responding to requests, supporting the BDI (Belief-Desire-Intention)
    model for agent autonomy.

    Per design doc section 3 - Autonomy Protocol.
    """
    response_type: ResponseType = Field(
        description="Type of response: ANSWER, PARTIAL, CLARIFY, REDIRECT, REFUSE, CONSULT"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Agent's confidence in response (0.0-1.0)"
    )
    findings: Optional[str] = Field(
        default=None,
        description="What the agent found (if any)"
    )
    reasoning: str = Field(
        description="Why the agent is responding this way"
    )

    # For CLARIFY response type
    clarification_questions: Optional[List[str]] = Field(
        default=None,
        description="Specific questions to ask for clarification"
    )

    # For REDIRECT or CONSULT response types
    suggested_agent: Optional[str] = Field(
        default=None,
        description="Which agent to redirect to or consult"
    )
    consultation_reason: Optional[str] = Field(
        default=None,
        description="Why consulting another agent would help"
    )

    # For PARTIAL response type
    missing_information: Optional[str] = Field(
        default=None,
        description="What information is missing for a complete answer"
    )

    # Metadata
    agent_id: str = Field(
        description="Identifier of the responding agent"
    )
    round_number: int = Field(
        default=0,
        description="Which round of dialogue this response is from"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the response was generated"
    )

    @field_serializer('timestamp')
    def serialize_response_timestamp(self, value: datetime) -> str:
        """Serialize datetime to ISO format string for JSON compatibility."""
        return value.isoformat() if value else None


class DiagnosisSession(BaseModel):
    """
    Tracks state across multi-round diagnosis dialogue.

    This schema manages the accumulated context, agent responses,
    and termination conditions for multi-round agent collaboration.

    Per design doc section 4 - Multi-Round Dialogue Protocol.
    """
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique session identifier"
    )
    original_query: str = Field(
        description="The user's original query that initiated the session"
    )
    current_round: int = Field(
        default=0,
        description="Current round number (0-indexed)"
    )
    max_rounds: int = Field(
        default=4,
        description="Maximum rounds before forced termination"
    )

    # Accumulated findings
    agent_responses: List[AgentResponse] = Field(
        default_factory=list,
        description="All responses from agents during this session"
    )
    reasoning_chain: List[str] = Field(
        default_factory=list,
        description="Accumulated reasoning steps for transparency"
    )

    # State tracking
    agents_consulted: List[str] = Field(
        default_factory=list,
        description="List of agents that have been consulted"
    )
    pending_clarifications: List[str] = Field(
        default_factory=list,
        description="Clarification questions waiting for user response"
    )
    current_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Current aggregate confidence level"
    )

    # Termination
    is_complete: bool = Field(
        default=False,
        description="Whether the session has reached a conclusion"
    )
    termination_reason: Optional[str] = Field(
        default=None,
        description="Why session ended: 'confidence_reached', 'max_rounds', 'all_consulted', 'user_clarification_needed'"
    )

    # Final synthesis
    final_diagnosis: Optional[str] = Field(
        default=None,
        description="Synthesized diagnosis after session completes"
    )
    recommended_actions: Optional[List[str]] = Field(
        default=None,
        description="Recommended actions based on diagnosis"
    )

    def add_agent_response(self, response: AgentResponse) -> None:
        """Add a response and update session state."""
        self.agent_responses.append(response)
        self.current_round = response.round_number

        if response.agent_id not in self.agents_consulted:
            self.agents_consulted.append(response.agent_id)

        if response.reasoning:
            self.reasoning_chain.append(
                f"[Round {response.round_number}] {response.agent_id}: {response.reasoning}"
            )

        # Update confidence (take highest seen)
        if response.confidence > self.current_confidence:
            self.current_confidence = response.confidence

    def should_terminate(self) -> bool:
        """Check if session should terminate."""
        if self.is_complete:
            return True

        # High confidence reached
        if self.current_confidence >= 0.8 and self.agent_responses:
            last_response = self.agent_responses[-1]
            if last_response.response_type == ResponseType.ANSWER:
                self.termination_reason = "confidence_reached"
                return True

        # Max rounds reached
        if self.current_round >= self.max_rounds:
            self.termination_reason = "max_rounds"
            return True

        return False

    class Config:
        arbitrary_types_allowed = True


class ConsultPayload(BaseModel):
    """
    Validated payload for /consult requests.

    Provides input validation for the payload dictionary in AgentCard,
    ensuring queries meet length requirements and optional fields have
    sensible defaults and constraints.
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The consultation query text"
    )
    # MRI-specific fields
    customer_id: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Siemens Customer ID (e.g., 'mr200103')"
    )
    scanner_model: Optional[str] = Field(
        default=None,
        max_length=100,
        description="MRI scanner model (e.g., 'MAGNETOM Sola', 'XA50', 'XA60')"
    )
    institution_type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Institution type: 'academic', 'private', 'cancer_center'"
    )
    # Legacy fields (preserved for backward compatibility)
    location: Optional[str] = Field(
        default="unknown",
        max_length=200,
        description="Geographic location context"
    )
    is_symptom: bool = Field(
        default=True,
        description="Whether the query describes a symptom"
    )
    equipment_type: Optional[str] = Field(
        default="MRI",
        max_length=200,
        description="Type of equipment involved"
    )
    station_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Charging station identifier (legacy)"
    )
    timestamp: Optional[str] = Field(
        default="",
        max_length=50,
        description="Timestamp of the event/issue"
    )
    delegated_by: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Agent that delegated this request"
    )
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional context information"
    )

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "ConsultPayload":
        """
        Create a ConsultPayload from a raw payload dictionary.

        Args:
            payload: Raw payload dictionary from AgentCard

        Returns:
            Validated ConsultPayload instance

        Raises:
            ValueError: If validation fails
        """
        return cls(**payload)


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

    @field_serializer('last_query_time')
    def serialize_last_query_time(self, value: Optional[datetime]) -> Optional[str]:
        """Serialize datetime to ISO format string for JSON compatibility."""
        return value.isoformat() if value else None


class DiagnoseRequest(BaseModel):
    """
    Request model for the /diagnose endpoint (multi-round diagnosis).

    Used to initiate or continue a multi-round diagnosis session.
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The diagnosis query or symptom description"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Existing session ID to continue (for clarification responses)"
    )
    location: Optional[str] = Field(
        default="unknown",
        description="Location context"
    )
    equipment_type: Optional[str] = Field(
        default="MRI",
        description="Type of equipment involved"
    )
    clarification_response: Optional[str] = Field(
        default=None,
        description="User's response to a clarification question"
    )
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional context information"
    )


class DiagnoseResponse(BaseModel):
    """
    Response model from the /diagnose endpoint.

    Contains the full session state including all agent responses,
    reasoning chain, and final diagnosis if complete.
    """
    success: bool = Field(description="Whether the request was processed successfully")
    session: DiagnosisSession = Field(description="Full session state")
    processing_time_ms: float = Field(description="Total processing time")
    error: Optional[str] = Field(default=None, description="Error message if failed")

    @property
    def is_complete(self) -> bool:
        """Check if diagnosis is complete."""
        return self.session.is_complete

    @property
    def needs_clarification(self) -> bool:
        """Check if user clarification is needed."""
        return len(self.session.pending_clarifications) > 0
