"""
Shared Output Schema for Multi-Agent System

Defines standardized JSON output formats so all agents produce mergeable findings.
Used by the Reporting/Orchestration layer to combine insights from:
- Agent 1 (The Specialist): diagnostic findings
- Agent 2 (The Anthropologist): contextual findings
- Agent 3 (The Auditor): compliance findings

Author: Thesis Project - Agentic Infra Co-Pilot
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_serializer
import uuid


class FindingCategory(str, Enum):
    """Categories of agent findings."""
    DIAGNOSTIC = "diagnostic"       # From Agent 1: technical errors, DICOM issues
    CONTEXTUAL = "contextual"       # From Agent 2: workflow, institution context
    COMPLIANCE = "compliance"       # From Agent 3: safety, SOP compliance


class Severity(str, Enum):
    """Severity levels for findings."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentFinding(BaseModel):
    """Standardized finding from any agent."""
    finding_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_id: str = Field(description="Which agent produced this finding")
    agent_role: str = Field(description="'specialist', 'anthropologist', or 'auditor'")
    category: FindingCategory
    finding: str = Field(description="The core finding or conclusion")
    evidence: List[str] = Field(
        default_factory=list,
        description="Supporting evidence citations (document names, log entries, etc.)"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Agent confidence in this finding")
    severity: Optional[Severity] = None
    customer_id: Optional[str] = Field(default=None, description="Related Siemens Customer ID")
    scanner_model: Optional[str] = Field(default=None, description="Related MRI scanner model")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat() if value else None


class ComplianceStatus(str, Enum):
    """Overall compliance status for a merged report."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    NEEDS_REVIEW = "needs_review"
    NOT_ASSESSED = "not_assessed"


class MergedReport(BaseModel):
    """Combined report from all agents for a single query."""
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str = Field(description="Original user query")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Findings from all agents
    findings: List[AgentFinding] = Field(default_factory=list)

    # Integrated analysis
    integrated_summary: Optional[str] = Field(
        default=None,
        description="Unified summary combining all agent findings"
    )
    recommended_actions: List[str] = Field(default_factory=list)
    compliance_status: ComplianceStatus = Field(default=ComplianceStatus.NOT_ASSESSED)

    # References
    customer_ids_referenced: List[str] = Field(default_factory=list)
    documents_cited: List[str] = Field(default_factory=list)

    # Metadata
    total_processing_time_ms: float = Field(default=0.0)
    agents_consulted: List[str] = Field(default_factory=list)

    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat() if value else None

    def add_finding(self, finding: AgentFinding) -> None:
        """Add a finding and update report metadata."""
        self.findings.append(finding)
        if finding.agent_id not in self.agents_consulted:
            self.agents_consulted.append(finding.agent_id)
        if finding.customer_id and finding.customer_id not in self.customer_ids_referenced:
            self.customer_ids_referenced.append(finding.customer_id)
        for evidence in finding.evidence:
            if evidence not in self.documents_cited:
                self.documents_cited.append(evidence)

    def get_findings_by_category(self, category: FindingCategory) -> List[AgentFinding]:
        """Filter findings by category."""
        return [f for f in self.findings if f.category == category]

    def get_highest_severity(self) -> Optional[Severity]:
        """Get the highest severity across all findings."""
        severity_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]
        for sev in severity_order:
            if any(f.severity == sev for f in self.findings):
                return sev
        return None

    def to_json(self) -> str:
        """Serialize to JSON for reporting."""
        return self.model_dump_json(indent=2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()
