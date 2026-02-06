"""
Diagnosis Logging - JSON Logging Infrastructure for Visualization

Provides structured logging for diagnosis sessions to enable:
- Reasoning chain diagrams (section 7.2)
- Confidence progression charts (section 7.3)
- Cross-domain reference heatmaps (section 7.4)
- Ablation comparison data

Per design doc section 7 - Visualizations.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RoundLog(BaseModel):
    """Log for a single round of agent interaction."""
    round_number: int = Field(description="Which round (0-indexed)")
    agent: str = Field(description="Agent that responded")
    response_type: str = Field(description="ANSWER, PARTIAL, CLARIFY, etc.")
    confidence: float = Field(description="Agent's confidence 0.0-1.0")
    findings_summary: str = Field(description="Summary of findings (truncated)")
    cited_agents: List[str] = Field(
        default_factory=list,
        description="Other agents referenced in response (for emergence tracking)"
    )
    latency_ms: float = Field(description="Response latency in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CrossDomainReference(BaseModel):
    """Tracks cross-domain citations for emergence detection."""
    from_agent: str = Field(description="Agent making the reference")
    to_agent: str = Field(description="Agent being referenced")
    reference_type: str = Field(
        description="Type: 'builds_on', 'contradicts', 'confirms', 'consults'"
    )
    content_snippet: str = Field(description="Relevant text showing reference")
    round_number: int = Field(description="Which round this occurred")


class ReasoningStep(BaseModel):
    """Single step in the reasoning chain."""
    step_number: int
    agent: str
    action: str = Field(description="What the agent did/concluded")
    evidence: str = Field(description="Supporting evidence for the step")
    leads_to: Optional[str] = Field(
        default=None,
        description="Next step or conclusion this enables"
    )


class DiagnosisLog(BaseModel):
    """
    Complete log for a diagnosis session.

    Captures all data needed for visualization and analysis.
    """
    session_id: str = Field(description="Unique session identifier")
    test_case_id: Optional[str] = Field(
        default=None,
        description="Test case identifier if from test suite"
    )
    mode: str = Field(
        default="mas_full",
        description="Ablation mode: governance_only, hardware_only, telemetry_only, single_all_data, mas_full"
    )

    # Original query
    original_query: str = Field(description="User's original query")
    query_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional query context (location, equipment, etc.)"
    )

    # Per-round tracking
    rounds: List[RoundLog] = Field(
        default_factory=list,
        description="Log of each dialogue round"
    )

    # Final outcomes
    final_diagnosis: str = Field(description="Synthesized final diagnosis")
    ground_truth: Optional[str] = Field(
        default=None,
        description="Expected correct diagnosis (for test cases)"
    )
    accuracy_score: Optional[float] = Field(
        default=None,
        description="Automated accuracy score 0.0-1.0"
    )

    # Emergence evidence
    cross_domain_refs: List[CrossDomainReference] = Field(
        default_factory=list,
        description="Cross-domain references for emergence tracking"
    )
    reasoning_chain: List[ReasoningStep] = Field(
        default_factory=list,
        description="Full reasoning chain"
    )

    # Performance metrics
    total_latency_ms: float = Field(
        default=0.0,
        description="End-to-end processing time"
    )
    total_rounds: int = Field(
        default=0,
        description="Number of dialogue rounds"
    )
    tokens_consumed: Optional[int] = Field(
        default=None,
        description="Total LLM tokens used (for cost tracking)"
    )

    # Evaluation metadata
    termination_reason: str = Field(
        default="unknown",
        description="Why session ended"
    )
    agents_consulted: List[str] = Field(
        default_factory=list,
        description="List of agents involved"
    )
    max_confidence_reached: float = Field(
        default=0.0,
        description="Highest confidence during session"
    )

    # Timestamps
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def add_round(self, round_log: RoundLog) -> None:
        """Add a round log and update metrics."""
        self.rounds.append(round_log)
        self.total_rounds = len(self.rounds)
        self.total_latency_ms += round_log.latency_ms

        if round_log.confidence > self.max_confidence_reached:
            self.max_confidence_reached = round_log.confidence

        if round_log.agent not in self.agents_consulted:
            self.agents_consulted.append(round_log.agent)

    def detect_cross_domain_references(self) -> None:
        """Analyze rounds to detect cross-domain references."""
        agent_findings: Dict[str, str] = {}

        for round_log in self.rounds:
            findings = round_log.findings_summary.lower()
            agent_findings[round_log.agent] = findings

            # Check if this agent references other agents
            for other_agent, other_findings in agent_findings.items():
                if other_agent == round_log.agent:
                    continue

                # Simple keyword matching for demonstration
                # In production, use semantic similarity
                other_keywords = set(other_findings.split())
                current_keywords = set(findings.split())
                overlap = other_keywords & current_keywords

                if len(overlap) > 2:  # Significant overlap
                    ref_type = self._determine_reference_type(findings, other_findings)
                    self.cross_domain_refs.append(CrossDomainReference(
                        from_agent=round_log.agent,
                        to_agent=other_agent,
                        reference_type=ref_type,
                        content_snippet=f"Overlap: {', '.join(list(overlap)[:5])}",
                        round_number=round_log.round_number
                    ))
                    round_log.cited_agents.append(other_agent)

    def _determine_reference_type(self, current: str, other: str) -> str:
        """Determine how current findings relate to other findings."""
        if any(w in current for w in ['confirms', 'agrees', 'consistent']):
            return 'confirms'
        if any(w in current for w in ['contradicts', 'disagrees', 'however']):
            return 'contradicts'
        if any(w in current for w in ['consult', 'ask', 'check with']):
            return 'consults'
        return 'builds_on'

    def build_reasoning_chain(self) -> None:
        """Construct reasoning chain from rounds."""
        for i, round_log in enumerate(self.rounds):
            step = ReasoningStep(
                step_number=i + 1,
                agent=round_log.agent,
                action=round_log.findings_summary[:200],
                evidence=f"Confidence: {round_log.confidence}, Type: {round_log.response_type}",
                leads_to=self.rounds[i + 1].agent if i + 1 < len(self.rounds) else "Final Diagnosis"
            )
            self.reasoning_chain.append(step)

    def get_confidence_progression(self) -> List[Dict[str, Any]]:
        """Get data for confidence progression chart."""
        return [
            {
                'round': r.round_number,
                'agent': r.agent,
                'confidence': r.confidence,
                'response_type': r.response_type
            }
            for r in self.rounds
        ]

    def get_emergence_score(self) -> float:
        """
        Calculate emergence score based on cross-domain references.

        Higher score = more emergence evidence.
        """
        if not self.cross_domain_refs:
            return 0.0

        unique_pairs = set()
        for ref in self.cross_domain_refs:
            pair = tuple(sorted([ref.from_agent, ref.to_agent]))
            unique_pairs.add(pair)

        # Score based on unique agent pairs that communicated
        max_pairs = 3  # 3 agents = 3 possible pairs
        return len(unique_pairs) / max_pairs

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DiagnosisLogger:
    """Logger for managing diagnosis log files."""

    def __init__(self, log_dir: str = "logs/diagnosis"):
        """Initialize logger with output directory."""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def save_log(self, log: DiagnosisLog) -> str:
        """
        Save diagnosis log to JSON file.

        Returns:
            Path to saved file
        """
        log.completed_at = datetime.utcnow()
        log.detect_cross_domain_references()
        log.build_reasoning_chain()

        filename = f"{log.session_id}_{log.mode}.json"
        filepath = self.log_dir / filename

        with open(filepath, 'w') as f:
            json.dump(log.model_dump(), f, indent=2, default=str)

        logger.info(f"Saved diagnosis log: {filepath}")
        return str(filepath)

    def load_log(self, filepath: str) -> DiagnosisLog:
        """Load diagnosis log from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return DiagnosisLog(**data)

    def list_logs(self, test_case_id: Optional[str] = None) -> List[str]:
        """List all log files, optionally filtered by test case."""
        logs = list(self.log_dir.glob("*.json"))

        if test_case_id:
            # Filter logs that match test case
            filtered = []
            for log_path in logs:
                try:
                    log = self.load_log(str(log_path))
                    if log.test_case_id == test_case_id:
                        filtered.append(str(log_path))
                except Exception:
                    continue
            return filtered

        return [str(p) for p in logs]

    def get_ablation_logs(self, test_case_id: str) -> Dict[str, DiagnosisLog]:
        """Get all ablation mode logs for a test case."""
        result = {}
        logs = self.list_logs(test_case_id)

        for log_path in logs:
            log = self.load_log(log_path)
            result[log.mode] = log

        return result


def main():
    """Test the diagnosis logging infrastructure."""
    logger.info("=" * 60)
    logger.info("Testing Diagnosis Logging Infrastructure")
    logger.info("=" * 60)

    # Create sample log
    log = DiagnosisLog(
        session_id="test-session-001",
        test_case_id="cascading_thermal_fault",
        mode="mas_full",
        original_query="MRI thermal shutdown every 90 minutes",
        query_metadata={"location": "Radiology", "equipment": "Siemens MRI"}
    )

    # Add sample rounds
    log.add_round(RoundLog(
        round_number=0,
        agent="governance_agent",
        response_type="partial",
        confidence=0.4,
        findings_summary="SLA breach detected at 94% uptime",
        latency_ms=1500
    ))

    log.add_round(RoundLog(
        round_number=1,
        agent="telemetry_agent",
        response_type="consult",
        confidence=0.6,
        findings_summary="90-minute pattern detected in session failures",
        cited_agents=["governance_agent"],
        latency_ms=2000
    ))

    log.add_round(RoundLog(
        round_number=2,
        agent="hardware_agent",
        response_type="answer",
        confidence=0.85,
        findings_summary="Thermal sensor calibration drift matches 90-minute cycle",
        cited_agents=["telemetry_agent"],
        latency_ms=1800
    ))

    log.final_diagnosis = "Sensor calibration issue causing thermal shutdowns"
    log.ground_truth = "Sensor calibration drift"
    log.termination_reason = "confidence_reached"

    # Analyze and save
    log.detect_cross_domain_references()
    log.build_reasoning_chain()

    logger.info(f"\nSession ID: {log.session_id}")
    logger.info(f"Total Rounds: {log.total_rounds}")
    logger.info(f"Agents Consulted: {log.agents_consulted}")
    logger.info(f"Max Confidence: {log.max_confidence_reached}")
    logger.info(f"Emergence Score: {log.get_emergence_score()}")

    logger.info("\nConfidence Progression:")
    for point in log.get_confidence_progression():
        logger.info(f"  Round {point['round']}: {point['agent']} = {point['confidence']}")

    logger.info("\nCross-Domain References:")
    for ref in log.cross_domain_refs:
        logger.info(f"  {ref.from_agent} -> {ref.to_agent}: {ref.reference_type}")

    logger.info("\nReasoning Chain:")
    for step in log.reasoning_chain:
        logger.info(f"  Step {step.step_number}: {step.agent} -> {step.leads_to}")

    # Save to file
    diagnosis_logger = DiagnosisLogger()
    filepath = diagnosis_logger.save_log(log)
    logger.info(f"\nSaved to: {filepath}")

    logger.info("\n" + "=" * 60)
    logger.info("Logging infrastructure test complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
