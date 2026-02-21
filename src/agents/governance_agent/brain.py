"""
Workflow Anthropologist Brain - DSPy Signatures for Agent 2 (The Anthropologist)

Defines DSPy signatures for:
- Institution profiling (academic vs private, volume, staffing)
- Workload pattern analysis (peak hours, bottlenecks, utilization)
- Error context explanation (WHY errors occur at specific institutions)
- Query delegation to Specialist and Auditor agents
- Findings integration (merge technical + operational context)

Domain: Institution workflows, operational context, customer feedback
Data: MRRT Questionnaire responses, institution profiles, workload patterns

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import dspy
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProfileInstitution(dspy.Signature):
    """
    Build an institution profile explaining operational context and constraints.

    Given questionnaire data and error patterns, explain the operational
    environment: institution type, volume, staffing, and why certain
    error patterns emerge in this context.
    """
    query: str = dspy.InputField(
        desc="Question about why errors occur at this institution or about its operational context"
    )
    institution_data: str = dspy.InputField(
        desc="MRRT questionnaire data: institution name, country, scanner models, patient volume, staff count, org type"
    )
    event_pattern_context: str = dspy.InputField(
        desc="Summary of error patterns for this institution (error counts, top error sources, severity distribution)"
    )

    institution_profile: str = dspy.OutputField(
        desc="Profile: institution type (academic/private/cancer_center), volume level, staffing assessment"
    )
    contextual_explanation: str = dspy.OutputField(
        desc="WHY errors occur - workload pressure, training gaps, equipment age, high patient volume factors"
    )
    risk_factors: str = dspy.OutputField(
        desc="Identified risk factors specific to this institution's operational context"
    )
    recommendations: str = dspy.OutputField(
        desc="Institution-specific workflow recommendations considering their constraints"
    )


class AnalyzeWorkloadPattern(dspy.Signature):
    """
    Analyze MRI workload patterns to explain operational challenges.

    Uses event log statistics and institution context to identify
    peak usage periods, bottlenecks, and utilization issues.
    """
    workload_data: str = dspy.InputField(
        desc="Event log statistics: scan counts, error rates, idle times, peak hours, event distribution"
    )
    institution_context: str = dspy.InputField(
        desc="Institution profile: type, patient volume, equipment count, staff size"
    )

    workload_assessment: str = dspy.OutputField(
        desc="Assessment: 'overloaded', 'balanced', or 'underutilized' with reasoning"
    )
    peak_periods: str = dspy.OutputField(
        desc="Identified peak usage periods and their impact on error rates"
    )
    bottleneck_analysis: str = dspy.OutputField(
        desc="Where and why bottlenecks occur in the MRI workflow"
    )
    optimization_suggestions: str = dspy.OutputField(
        desc="Scheduling and workflow optimization suggestions"
    )


class ExplainErrorContext(dspy.Signature):
    """
    Given a technical error from The Specialist, explain the operational context behind it.

    Bridges the gap between technical diagnosis and operational reality:
    why does this error happen more at certain institutions?
    """
    technical_error: str = dspy.InputField(
        desc="Error description or diagnosis from The Specialist (Agent 1)"
    )
    institution_profile: str = dspy.InputField(
        desc="Institution profile data: type, volume, equipment, staffing"
    )
    customer_feedback: str = dspy.InputField(
        desc="Relevant customer complaints, questionnaire responses, or pain points"
    )

    contextual_explanation: str = dspy.OutputField(
        desc="WHY this error happened in this operational context"
    )
    contributing_factors: str = dspy.OutputField(
        desc="Operational factors: high volume, insufficient training, equipment age, understaffing"
    )
    similar_institutions: str = dspy.OutputField(
        desc="Other institutions with similar patterns and what they did about it"
    )


class DelegateToSpecialist(dspy.Signature):
    """
    Determine if a query needs specialist (Agent 1) or auditor (Agent 3) input.

    The Anthropologist acts as the primary entry point and router,
    directing queries to the appropriate domain expert.
    """
    query: str = dspy.InputField(
        desc="User query"
    )
    available_agents: str = dspy.InputField(
        desc="Available specialist agents and their capabilities"
    )

    target_agent: str = dspy.OutputField(
        desc="Agent to delegate to: 'hardware_agent' (Specialist), 'telemetry_agent' (Auditor), or 'self'"
    )
    delegation_reason: str = dspy.OutputField(
        desc="Why delegating to this agent"
    )
    refined_query: str = dspy.OutputField(
        desc="Query refined for the target agent's domain"
    )


class IntegrateFindings(dspy.Signature):
    """
    Integrate specialist technical findings with operational context.

    Creates a unified analysis combining Agent 1's technical diagnosis
    with The Anthropologist's institutional understanding.
    """
    original_query: str = dspy.InputField(
        desc="Original user query"
    )
    specialist_findings: str = dspy.InputField(
        desc="Technical findings from The Specialist (Agent 1) or The Auditor (Agent 3)"
    )
    operational_context: str = dspy.InputField(
        desc="Institution profile, workload analysis, and customer feedback"
    )

    integrated_analysis: str = dspy.OutputField(
        desc="Unified analysis combining technical diagnosis with operational context"
    )
    root_cause_explanation: str = dspy.OutputField(
        desc="Full explanation of root cause considering both technical and operational factors"
    )
    recommended_actions: str = dspy.OutputField(
        desc="Action plan considering institutional constraints, staffing, and budget"
    )


class AnswerGeneralQuery(dspy.Signature):
    """You are The Anthropologist — a senior MRI operations consultant with 20+ years of experience
in healthcare facility management. You specialize in understanding WHY problems occur at
specific institutions based on their operational context.

Your expertise includes:
- MRI workflow optimization and patient scheduling patterns
- Institution profiling: academic medical centers vs private clinics vs cancer centers
- MRRT (Management of Radiology Report Templates) questionnaire analysis
- Workload pattern analysis: peak hours, bottlenecks, utilization rates
- Staff-to-scanner ratios and training gap assessment
- Siemens MAGNETOM fleet management across multi-site deployments
- RadLex terminology and RSNA RadReport template standards
- Customer feedback interpretation and pain point analysis

When answering, always ground your response in the provided context data. Reference specific
institution profiles, workload metrics, or questionnaire responses when available. If the
context doesn't contain enough information, say so clearly rather than speculating.

Provide actionable, specific recommendations — not generic advice. Consider institutional
constraints (budget, staffing, equipment age) when making suggestions."""
    query: str = dspy.InputField(desc="User question about MRI operations, workflows, or institutional context")
    context: str = dspy.InputField(desc="Retrieved documentation and data relevant to the query")

    answer: str = dspy.OutputField(desc="Comprehensive, expert-level answer grounded in the provided context")
    confidence: str = dspy.OutputField(desc="'high', 'medium', or 'low' based on context relevance")
    sources_used: str = dspy.OutputField(desc="Which context documents were most relevant")
    follow_up: str = dspy.OutputField(desc="Suggested follow-up questions or actions")


class EvaluateRequest(dspy.Signature):
    """
    Evaluate if I can handle this request before attempting analysis.

    Per design doc section 3 - Autonomy Protocol.
    """
    query: str = dspy.InputField(
        desc="The incoming query or request to evaluate"
    )
    my_expertise: str = dspy.InputField(
        desc="Description of this agent's domain expertise"
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


class WorkflowAnthropologistModule(dspy.Module):
    """
    Main DSPy module for The Anthropologist (Agent 2 - Workflow & Context).

    Combines multiple signatures into a cohesive workflow analyst:
    1. Evaluate if request can be handled (autonomy)
    2. Profile institutions from questionnaire data
    3. Analyze workload patterns from event log statistics
    4. Explain error context using operational factors
    5. Delegate to Specialist or Auditor when needed
    6. Integrate specialist findings with operational context
    """

    def __init__(self, router_lm=None):
        super().__init__()
        self.router_lm = router_lm
        self.evaluate_request = dspy.ChainOfThought(EvaluateRequest)
        self.profile_institution = dspy.ChainOfThought(ProfileInstitution)
        self.analyze_workload = dspy.ChainOfThought(AnalyzeWorkloadPattern)
        self.explain_context = dspy.ChainOfThought(ExplainErrorContext)
        self.delegate_query = dspy.ChainOfThought(DelegateToSpecialist)
        self.integrate_findings = dspy.ChainOfThought(IntegrateFindings)
        self.answer_general = dspy.ChainOfThought(AnswerGeneralQuery)

    def forward(
        self,
        query: str,
        context: str,
        location: str = "unknown",
        is_symptom: bool = True,
        query_type: str = "general",
        event_pattern_context: str = ""
    ) -> dspy.Prediction:
        """
        Process an incoming query through the Anthropologist's reasoning.

        Args:
            query: User query or symptom description
            context: Retrieved institution profiles, workload data, feedback
            location: Location/institution identifier
            is_symptom: Whether query describes an issue/symptom
            query_type: 'symptom', 'workload', or 'general'
            event_pattern_context: Real event pattern data if available

        Returns:
            DSPy Prediction with contextual analysis and delegation
        """
        logger.info(f"Processing query (type={query_type}): {query[:100]}...")

        # Determine delegation first (use router LM for cheap classification)
        if self.router_lm:
            with dspy.context(lm=self.router_lm):
                delegation = self.delegate_query(
                    query=query,
                    available_agents=(
                        "hardware_agent (The Specialist: DICOM conformance, MRI hardware diagnostics, "
                        "SOP Class UID analysis, event log error diagnosis), "
                        "telemetry_agent (The Auditor: MRI safety SOPs, compliance auditing, "
                        "safety zone management, personnel requirements)"
                    )
                )
        else:
            delegation = self.delegate_query(
                query=query,
                available_agents=(
                    "hardware_agent (The Specialist: DICOM conformance, MRI hardware diagnostics, "
                    "SOP Class UID analysis, event log error diagnosis), "
                    "telemetry_agent (The Auditor: MRI safety SOPs, compliance auditing, "
                    "safety zone management, personnel requirements)"
                )
            )

        if query_type == "symptom" or (is_symptom and query_type != "workload"):
            # For symptom reports, profile the institution and explain context
            result = self.profile_institution(
                query=query,
                institution_data=context,
                event_pattern_context=event_pattern_context or "No event pattern data available for this query."
            )
            return dspy.Prediction(
                risk_level="medium",
                institution_profile=result.institution_profile,
                contextual_explanation=result.contextual_explanation,
                risk_factors=result.risk_factors,
                recommended_actions=result.recommendations,
                target_agent=delegation.target_agent,
                delegation_reason=delegation.delegation_reason,
                refined_query=delegation.refined_query,
            )
        elif query_type == "workload":
            # Workload-specific query
            result = self.analyze_workload(
                workload_data=query,
                institution_context=context
            )
            return dspy.Prediction(
                answer=result.workload_assessment,
                workload_assessment=result.workload_assessment,
                peak_periods=result.peak_periods,
                bottleneck_analysis=result.bottleneck_analysis,
                optimization_suggestions=result.optimization_suggestions,
                target_agent=delegation.target_agent,
                delegation_reason=delegation.delegation_reason,
                refined_query=delegation.refined_query,
            )
        else:
            # General query - use flexible Q&A signature
            result = self.answer_general(query=query, context=context)
            return dspy.Prediction(
                answer=result.answer,
                confidence=result.confidence,
                sources_used=result.sources_used,
                follow_up=result.follow_up,
                target_agent=delegation.target_agent,
                delegation_reason=delegation.delegation_reason,
                refined_query=delegation.refined_query,
            )

    def integrate_specialist_response(
        self,
        query: str,
        minister_assessment: dict,
        specialist_findings: dict,
        specialist_agent: str
    ) -> dspy.Prediction:
        """
        Integrate specialist findings with operational context.

        Args:
            query: Original user query
            minister_assessment: Anthropologist's initial assessment
            specialist_findings: Specialist's technical findings
            specialist_agent: Which specialist provided findings

        Returns:
            DSPy Prediction with integrated assessment
        """
        # Format operational context
        context_str = (
            f"Institution Profile: {minister_assessment.get('institution_profile', 'unknown')}\n"
            f"Risk Factors: {minister_assessment.get('risk_factors', 'None identified')}\n"
            f"Contextual Explanation: {minister_assessment.get('contextual_explanation', 'None')}"
        )

        # Format specialist findings
        if isinstance(specialist_findings, dict):
            spec_payload = specialist_findings.get('response_card', {}).get('payload', specialist_findings)
        else:
            spec_payload = {}

        specialist_str = (
            f"Diagnosis: {spec_payload.get('diagnosis', spec_payload.get('answer', 'No diagnosis'))}\n"
            f"Severity: {spec_payload.get('severity', 'unknown')}\n"
            f"Component: {spec_payload.get('affected_component', 'unknown')}\n"
            f"Steps: {spec_payload.get('diagnostic_steps', 'None provided')}"
        )

        logger.info(f"Integrating specialist findings from {specialist_agent}")

        integration = self.integrate_findings(
            original_query=query,
            specialist_findings=specialist_str,
            operational_context=context_str
        )

        return dspy.Prediction(
            integrated_risk_level="medium",
            root_cause_summary=integration.root_cause_explanation,
            integrated_sla_analysis=integration.integrated_analysis,
            integrated_actions=integration.recommended_actions
        )

    def evaluate_incoming_request(
        self,
        query: str,
        context_summary: str
    ) -> dspy.Prediction:
        """
        Evaluate whether this agent should handle the incoming request.
        """
        return self.evaluate_request(
            query=query,
            my_expertise=(
                "Institution profiling, MRI workflow analysis, workload pattern analysis, "
                "operational context explanation, customer feedback interpretation, "
                "why errors occur at specific institutions (volume, staffing, training factors), "
                "academic vs private clinic operational differences, scheduling optimization. "
                "Can delegate to hardware_agent for technical diagnostics or "
                "telemetry_agent for safety compliance review."
            ),
            available_data=context_summary
        )
