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
        desc="Which specialist agent to consult: 'hardware_agent', 'telemetry_agent', or 'none'"
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
        desc="Agent to delegate to: 'hardware_agent', 'telemetry_agent', or 'self'"
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


class IntegrateSpecialistFindings(dspy.Signature):
    """
    Integrate specialist agent findings with governance assessment.

    This signature creates a coherent, unified response that:
    1. Combines the Minister's SLA/policy analysis with specialist technical findings
    2. Ensures the root cause and recommended actions are consistent
    3. Provides clear, actionable recommendations

    Used AFTER receiving specialist response to improve information integration.
    """
    original_query: str = dspy.InputField(
        desc="The user's original query or symptom report"
    )
    minister_assessment: str = dspy.InputField(
        desc="Minister's initial assessment including risk level, violated SLAs, and recommendations"
    )
    specialist_findings: str = dspy.InputField(
        desc="Specialist agent's technical diagnosis, severity assessment, and recommended diagnostic steps"
    )
    specialist_agent: str = dspy.InputField(
        desc="Which specialist provided the findings (hardware_agent or telemetry_agent)"
    )

    integrated_risk_level: str = dspy.OutputField(
        desc="Final risk level considering both governance and technical perspectives: 'low', 'medium', 'high', or 'critical'"
    )
    root_cause_summary: str = dspy.OutputField(
        desc="Coherent summary of the root cause combining SLA violations and technical diagnosis"
    )
    integrated_sla_analysis: str = dspy.OutputField(
        desc="Complete SLA analysis incorporating specialist findings"
    )
    integrated_actions: str = dspy.OutputField(
        desc="Unified action plan combining governance requirements and technical remediation steps"
    )


class EvaluateRequest(dspy.Signature):
    """
    Evaluate if I can handle this request before attempting diagnosis.

    This signature enables agent autonomy by allowing the agent to:
    1. Assess if the query falls within its expertise
    2. Determine confidence level for potential response
    3. Suggest alternative agents if better suited
    4. Request clarification or consultation if needed

    Per design doc section 3 - Autonomy Protocol.
    """
    query: str = dspy.InputField(
        desc="The incoming query or request to evaluate"
    )
    my_expertise: str = dspy.InputField(
        desc="Description of this agent's domain expertise (e.g., 'SLA compliance, network intent, governance policies')"
    )
    available_data: str = dspy.InputField(
        desc="Summary of retrieved context and available documents"
    )

    can_fully_answer: bool = dspy.OutputField(
        desc="True if agent can provide a complete, confident answer"
    )
    confidence_level: float = dspy.OutputField(
        desc="Confidence score from 0.0 to 1.0"
    )
    response_type: str = dspy.OutputField(
        desc="Response type: 'answer', 'partial', 'clarify', 'redirect', 'refuse', or 'consult'"
    )
    reasoning: str = dspy.OutputField(
        desc="Brief explanation of the evaluation decision"
    )
    suggested_agent: str = dspy.OutputField(
        desc="If redirect/consult needed: 'hardware_agent', 'telemetry_agent', or 'none'"
    )
    missing_info: str = dspy.OutputField(
        desc="If partial/clarify: what information is missing or needed"
    )


class TelekomMinisterModule(dspy.Module):
    """
    Main DSPy module for Telekom Minister agent (Governance Agent).

    Combines multiple signatures into a cohesive reasoning flow:
    1. Evaluate if request can be handled (autonomy)
    2. Assess risk if symptom/issue is reported
    3. Delegate to specialists if needed
    4. Integrate specialist findings with governance assessment
    5. Synthesize coherent final response
    """

    def __init__(self):
        super().__init__()
        self.evaluate_request = dspy.ChainOfThought(EvaluateRequest)
        self.assess_risk = dspy.ChainOfThought(AssessRisk)
        self.validate_intent = dspy.ChainOfThought(ValidateIntent)
        self.delegate_query = dspy.ChainOfThought(DelegateQuery)
        self.synthesize = dspy.ChainOfThought(SynthesizeResponse)
        self.integrate_findings = dspy.ChainOfThought(IntegrateSpecialistFindings)

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
                "hardware_agent (MRI hardware specifications, Siemens equipment manuals, "
                "thermal sensors, gradient coils, technical diagnostics), "
                "telemetry_agent (MRI event logs, session monitoring, "
                "temporal fault patterns, anomaly detection)"
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

    def integrate_specialist_response(
        self,
        query: str,
        minister_assessment: dict,
        specialist_findings: dict,
        specialist_agent: str
    ) -> dspy.Prediction:
        """
        Integrate specialist findings with Minister's governance assessment.

        This creates a coherent, unified response by:
        1. Combining SLA/policy analysis with technical diagnosis
        2. Reconciling risk levels between governance and technical perspectives
        3. Creating unified, actionable recommendations

        Args:
            query: Original user query
            minister_assessment: Minister's initial assessment dict with
                                 risk_level, violated_slas, recommended_actions
            specialist_findings: Specialist's response dict with
                                 diagnosis, severity, diagnostic_steps
            specialist_agent: Name of specialist agent

        Returns:
            DSPy Prediction with integrated assessment
        """
        # Format minister assessment as string
        minister_str = (
            f"Risk Level: {minister_assessment.get('risk_level', 'unknown')}\n"
            f"Violated SLAs: {minister_assessment.get('violated_slas', 'None identified')}\n"
            f"Recommended Actions: {minister_assessment.get('recommended_actions', 'None')}"
        )

        # Extract specialist payload (handle nested response structure)
        if isinstance(specialist_findings, dict):
            spec_payload = specialist_findings.get('response_card', {}).get('payload', specialist_findings)
        else:
            spec_payload = {}

        # Format specialist findings as string
        specialist_str = (
            f"Diagnosis: {spec_payload.get('diagnosis', spec_payload.get('answer', 'No diagnosis'))}\n"
            f"Severity: {spec_payload.get('severity', 'unknown')}\n"
            f"Diagnostic Steps: {spec_payload.get('diagnostic_steps', 'None provided')}\n"
            f"Requires Escalation: {spec_payload.get('requires_escalation', 'unknown')}"
        )

        logger.info(f"Integrating specialist findings from {specialist_agent}")

        integration = self.integrate_findings(
            original_query=query,
            minister_assessment=minister_str,
            specialist_findings=specialist_str,
            specialist_agent=specialist_agent
        )

        return dspy.Prediction(
            integrated_risk_level=integration.integrated_risk_level,
            root_cause_summary=integration.root_cause_summary,
            integrated_sla_analysis=integration.integrated_sla_analysis,
            integrated_actions=integration.integrated_actions
        )

    def evaluate_incoming_request(
        self,
        query: str,
        context_summary: str
    ) -> dspy.Prediction:
        """
        Evaluate whether this agent should handle the incoming request.

        This method enables agent autonomy by assessing:
        - Whether the query falls within governance/SLA domain
        - Confidence level for potential response
        - Whether to redirect to or consult specialist agents

        Args:
            query: The incoming query or request
            context_summary: Summary of retrieved context (e.g., "Retrieved 5 SLA documents")

        Returns:
            DSPy Prediction with:
                - can_fully_answer: bool
                - confidence_level: float 0.0-1.0
                - response_type: 'answer', 'partial', 'clarify', 'redirect', 'refuse', 'consult'
                - suggested_agent: 'hardware_agent', 'telemetry_agent', or 'none'
                - reasoning: explanation of decision
                - missing_info: what's missing if partial/clarify
        """
        return self.evaluate_request(
            query=query,
            my_expertise=(
                "SLA compliance assessment, Network Intent validation, "
                "risk assessment for infrastructure decisions, governance policies, "
                "latency/bandwidth/reliability requirements for microgrids and MRI equipment. "
                "Can delegate to hardware_agent for equipment issues or telemetry_agent for event logs."
            ),
            available_data=context_summary
        )
