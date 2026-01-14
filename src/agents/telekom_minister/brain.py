"""
Telekom Minister Brain - DSPy Signatures for Governance Agent

Defines DSPy signatures for:
- SLA compliance assessment
- Network Intent validation
- Risk assessment for infrastructure decisions
- Query delegation to specialist agents

Domain: High-level network Intent/SLA requirements
Data: Latency, bandwidth, reliability specs for microgrids and charging stations

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import dspy
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AssessRisk(dspy.Signature):
    """
    Assess the risk level of an infrastructure issue based on SLA requirements.

    Given a symptom report and relevant SLA documents, determine:
    1. Which SLA requirements are potentially violated
    2. The risk severity (low/medium/high/critical)
    3. Recommended immediate actions
    """
    symptom_description: str = dspy.InputField(
        desc="Description of the reported infrastructure symptom or issue"
    )
    sla_context: str = dspy.InputField(
        desc="Relevant SLA documentation excerpts"
    )
    location: str = dspy.InputField(
        desc="Location identifier (e.g., Koumassi microgrid)"
    )

    risk_level: str = dspy.OutputField(
        desc="Risk severity: 'low', 'medium', 'high', or 'critical'"
    )
    violated_slas: str = dspy.OutputField(
        desc="List of SLA requirements potentially violated"
    )
    recommended_actions: str = dspy.OutputField(
        desc="Immediate recommended actions"
    )
    delegation_needed: str = dspy.OutputField(
        desc="Which specialist agent to consult: 'siemens_technician', 'illigo_operator', or 'none'"
    )


class ValidateIntent(dspy.Signature):
    """
    Validate whether a proposed network change aligns with Intent requirements.

    Network Intent defines the desired state of the infrastructure.
    This signature checks if proposed changes maintain compliance.
    """
    proposed_change: str = dspy.InputField(
        desc="Description of the proposed network or infrastructure change"
    )
    intent_context: str = dspy.InputField(
        desc="Current network Intent documentation"
    )
    current_state: str = dspy.InputField(
        desc="Current infrastructure state description"
    )

    is_compliant: str = dspy.OutputField(
        desc="'compliant' or 'non-compliant'"
    )
    compliance_reasoning: str = dspy.OutputField(
        desc="Detailed reasoning for compliance decision"
    )
    required_approvals: str = dspy.OutputField(
        desc="List of approvals needed if any"
    )


class DelegateQuery(dspy.Signature):
    """
    Determine which specialist agent should handle a technical query.

    The Telekom Minister acts as a router, directing queries to the
    appropriate domain expert based on the query type.
    """
    query: str = dspy.InputField(
        desc="The user's query or symptom report"
    )
    available_agents: str = dspy.InputField(
        desc="List of available specialist agents and their domains"
    )

    target_agent: str = dspy.OutputField(
        desc="Agent to delegate to: 'siemens_technician', 'illigo_operator', or 'self'"
    )
    delegation_reason: str = dspy.OutputField(
        desc="Reason for delegation decision"
    )
    refined_query: str = dspy.OutputField(
        desc="Query refined for the target specialist"
    )


class SynthesizeResponse(dspy.Signature):
    """
    Synthesize a final response from retrieved SLA/Intent documents.

    Used when the Minister handles the query directly without delegation.
    """
    query: str = dspy.InputField(
        desc="The user's original query"
    )
    retrieved_context: str = dspy.InputField(
        desc="Retrieved SLA and Intent documentation"
    )
    location: str = dspy.InputField(
        desc="Location context if applicable"
    )

    answer: str = dspy.OutputField(
        desc="Direct answer to the query based on documentation"
    )
    confidence: str = dspy.OutputField(
        desc="Confidence level: 'high', 'medium', or 'low'"
    )
    sources_used: str = dspy.OutputField(
        desc="List of source documents referenced"
    )


class TelekomMinisterModule(dspy.Module):
    """
    Main DSPy module for Telekom Minister agent.

    Combines multiple signatures into a cohesive reasoning flow:
    1. Assess risk if symptom/issue is reported
    2. Delegate to specialists if needed
    3. Synthesize response if handled directly
    """

    def __init__(self):
        super().__init__()
        self.assess_risk = dspy.ChainOfThought(AssessRisk)
        self.validate_intent = dspy.ChainOfThought(ValidateIntent)
        self.delegate_query = dspy.ChainOfThought(DelegateQuery)
        self.synthesize = dspy.ChainOfThought(SynthesizeResponse)

    def forward(
        self,
        query: str,
        context: str,
        location: str = "unknown",
        is_symptom: bool = True
    ) -> dspy.Prediction:
        """
        Process an incoming query through the Minister's reasoning.

        Args:
            query: User query or symptom description
            context: Retrieved SLA/Intent documentation
            location: Location identifier
            is_symptom: Whether query describes an issue/symptom

        Returns:
            DSPy Prediction with risk assessment, delegation, and response
        """
        logger.info(f"Processing query: {query[:100]}...")

        # Determine delegation first
        delegation = self.delegate_query(
            query=query,
            available_agents=(
                "siemens_technician (hardware specifications, equipment manuals, "
                "technical diagnostics), illigo_operator (OCPP event logs, charging "
                "station faults, real-time monitoring)"
            )
        )

        # If it's a symptom/issue, assess risk
        if is_symptom:
            risk_assessment = self.assess_risk(
                symptom_description=query,
                sla_context=context,
                location=location
            )

            return dspy.Prediction(
                risk_level=risk_assessment.risk_level,
                violated_slas=risk_assessment.violated_slas,
                recommended_actions=risk_assessment.recommended_actions,
                target_agent=delegation.target_agent,
                delegation_reason=delegation.delegation_reason,
                refined_query=delegation.refined_query
            )
        else:
            # Direct query - synthesize response
            synthesis = self.synthesize(
                query=query,
                retrieved_context=context,
                location=location
            )

            return dspy.Prediction(
                answer=synthesis.answer,
                confidence=synthesis.confidence,
                sources_used=synthesis.sources_used,
                target_agent=delegation.target_agent,
                delegation_reason=delegation.delegation_reason,
                refined_query=delegation.refined_query
            )

    def assess_infrastructure_risk(
        self,
        symptom: str,
        sla_context: str,
        location: str
    ) -> dspy.Prediction:
        """
        Dedicated method for risk assessment.

        Args:
            symptom: Description of the infrastructure issue
            sla_context: Relevant SLA documentation
            location: Location of the issue

        Returns:
            DSPy Prediction with risk assessment
        """
        return self.assess_risk(
            symptom_description=symptom,
            sla_context=sla_context,
            location=location
        )

    def validate_network_change(
        self,
        proposed_change: str,
        intent_context: str,
        current_state: str
    ) -> dspy.Prediction:
        """
        Validate a proposed network change against Intent.

        Args:
            proposed_change: The change being proposed
            intent_context: Network Intent documentation
            current_state: Current infrastructure state

        Returns:
            DSPy Prediction with compliance decision
        """
        return self.validate_intent(
            proposed_change=proposed_change,
            intent_context=intent_context,
            current_state=current_state
        )
