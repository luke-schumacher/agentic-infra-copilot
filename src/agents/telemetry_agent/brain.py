"""
Safety Auditor Brain - DSPy Signatures for Agent 3 (The Auditor)

Defines DSPy signatures for:
- SOP compliance validation for proposed actions/workflow changes
- Safety review of diagnostic actions from Agent 1
- MRI safety zone compliance checking (Zone I-IV)
- Workflow change auditing for regulatory compliance

Domain: MRI safety procedures, SOP compliance, safety zone management
Data: MRI-SOP.pdf, SOP-MRI-Safety-Training, ACR criteria

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import dspy
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ValidateComplianceSOP(dspy.Signature):
    """
    Check if a proposed action or workflow change complies with MRI SOPs.

    Reviews proposed actions against safety procedures, minimum personnel
    requirements, and zone access rules from the MRI-SOP documentation.
    """
    proposed_action: str = dspy.InputField(
        desc="Proposed workflow change or corrective action (e.g., from The Specialist or The Anthropologist)"
    )
    sop_context: str = dspy.InputField(
        desc="Relevant MRI-SOP procedure excerpts and safety requirements"
    )
    safety_zone_info: str = dspy.InputField(
        desc="MRI safety zone definitions (Zone I-IV) and personnel requirements for the action"
    )

    is_compliant: str = dspy.OutputField(
        desc="'compliant', 'non-compliant', or 'needs-review'"
    )
    compliance_details: str = dspy.OutputField(
        desc="Specific SOP sections referenced and how the action aligns or conflicts"
    )
    safety_concerns: str = dspy.OutputField(
        desc="Any safety concerns with the proposed action"
    )
    required_personnel: str = dspy.OutputField(
        desc="Required personnel per SOP: minimum staffing, qualifications, and supervision needs"
    )
    recommended_modifications: str = dspy.OutputField(
        desc="How to modify the action to achieve full compliance if not currently compliant"
    )


class ReviewDiagnosticAction(dspy.Signature):
    """
    Review a diagnostic action proposed by The Specialist (Agent 1) for safety compliance.

    Ensures that proposed hardware interventions, calibrations, or service
    procedures meet safety requirements before execution.
    """
    diagnostic_action: str = dspy.InputField(
        desc="Diagnostic or corrective action from The Specialist (e.g., 'recalibrate thermal sensors')"
    )
    equipment_context: str = dspy.InputField(
        desc="MRI equipment details: scanner model, current operational state, location"
    )
    sop_requirements: str = dspy.InputField(
        desc="Relevant SOP requirements for this type of maintenance/diagnostic action"
    )

    safety_assessment: str = dspy.OutputField(
        desc="Safety assessment: 'safe', 'caution', or 'unsafe'"
    )
    sop_compliance: str = dspy.OutputField(
        desc="SOP compliance status and relevant procedure sections"
    )
    personnel_requirements: str = dspy.OutputField(
        desc="Required personnel: Level 1 or Level 2 MR personnel, service engineer, etc."
    )
    safety_checklist: str = dspy.OutputField(
        desc="Pre-action safety checklist items that must be verified"
    )


class CheckSafetyZone(dspy.Signature):
    """
    Verify safety zone compliance for an MRI-related activity.

    MRI facilities have 4 safety zones (I-IV) with increasing restriction.
    This signature checks that proposed activities respect zone boundaries.
    """
    activity: str = dspy.InputField(
        desc="Proposed activity or maintenance procedure"
    )
    zone_definitions: str = dspy.InputField(
        desc="MRI safety zone definitions: Zone I (public), II (reception), III (control room), IV (magnet room)"
    )
    current_conditions: str = dspy.InputField(
        desc="Current scanner state (scanning, idle, quenched) and environmental conditions"
    )

    zone_classification: str = dspy.OutputField(
        desc="Which safety zone(s) are involved in this activity"
    )
    access_requirements: str = dspy.OutputField(
        desc="Who can access and under what conditions"
    )
    screening_requirements: str = dspy.OutputField(
        desc="MRI safety screening requirements for personnel involved"
    )
    restrictions: str = dspy.OutputField(
        desc="Restrictions: prohibited items, required procedures, and safety precautions"
    )


class AuditWorkflowChange(dspy.Signature):
    """
    Audit a workflow change recommendation for regulatory and safety compliance.

    Reviews workflow optimization suggestions from The Anthropologist
    to ensure they don't compromise patient safety or regulatory compliance.
    """
    workflow_change: str = dspy.InputField(
        desc="Proposed workflow change from The Anthropologist (e.g., 'reduce patient prep overlap')"
    )
    safety_context: str = dspy.InputField(
        desc="Safety SOPs, training requirements, and zone rules relevant to this workflow"
    )
    institution_context: str = dspy.InputField(
        desc="Institution type (academic/private), current staffing levels, and equipment"
    )

    audit_result: str = dspy.OutputField(
        desc="'approved', 'conditionally-approved', or 'rejected'"
    )
    safety_gaps: str = dspy.OutputField(
        desc="Any safety gaps identified in the proposed workflow change"
    )
    training_requirements: str = dspy.OutputField(
        desc="Additional training needed for staff to safely implement the change"
    )
    documentation_requirements: str = dspy.OutputField(
        desc="Required documentation, approvals, and audit trail for the change"
    )


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
        desc="If redirect/consult needed: 'governance_agent', 'hardware_agent', or 'none'"
    )
    missing_info: str = dspy.OutputField(
        desc="If partial/clarify: what information is missing or needed"
    )


class SafetyAuditorModule(dspy.Module):
    """
    Main DSPy module for The Auditor (Agent 3 - Safety & Compliance).

    Combines multiple signatures into a cohesive safety compliance expert:
    1. Evaluate if request can be handled (autonomy)
    2. Validate proposed actions against MRI SOPs
    3. Review diagnostic actions from Agent 1 for safety
    4. Check safety zone compliance for activities
    5. Audit workflow changes from Agent 2 for regulatory compliance
    """

    def __init__(self):
        super().__init__()
        self.evaluate_request = dspy.ChainOfThought(EvaluateRequest)
        self.validate_compliance = dspy.ChainOfThought(ValidateComplianceSOP)
        self.review_action = dspy.ChainOfThought(ReviewDiagnosticAction)
        self.check_zone = dspy.ChainOfThought(CheckSafetyZone)
        self.audit_workflow = dspy.ChainOfThought(AuditWorkflowChange)

    def forward(
        self,
        query: str,
        context: str,
        query_type: str = "general",
        station_id: str = "unknown",
        timestamp: str = ""
    ) -> dspy.Prediction:
        """
        Process an incoming query through the Auditor's reasoning.

        Args:
            query: User query, proposed action, or safety question
            context: Retrieved safety SOPs, zone definitions, compliance docs
            query_type: 'compliance_check', 'action_review', 'safety_zone', 'workflow_audit', or 'general'
            station_id: Scanner/institution identifier if applicable
            timestamp: Timestamp if applicable

        Returns:
            DSPy Prediction with safety/compliance assessment
        """
        logger.info(f"Processing query (type={query_type}): {query[:100]}...")

        if query_type == "compliance_check":
            result = self.validate_compliance(
                proposed_action=query,
                sop_context=context,
                safety_zone_info="See SOP context for zone definitions."
            )
            return dspy.Prediction(
                is_compliant=result.is_compliant,
                compliance_details=result.compliance_details,
                safety_concerns=result.safety_concerns,
                required_personnel=result.required_personnel,
                answer=f"Compliance: {result.is_compliant}. {result.compliance_details}. Concerns: {result.safety_concerns}"
            )

        elif query_type == "action_review":
            result = self.review_action(
                diagnostic_action=query,
                equipment_context=station_id,
                sop_requirements=context
            )
            return dspy.Prediction(
                safety_assessment=result.safety_assessment,
                sop_compliance=result.sop_compliance,
                personnel_requirements=result.personnel_requirements,
                safety_checklist=result.safety_checklist,
                answer=f"Safety: {result.safety_assessment}. {result.sop_compliance}. Checklist: {result.safety_checklist}"
            )

        elif query_type == "safety_zone":
            result = self.check_zone(
                activity=query,
                zone_definitions=context,
                current_conditions=station_id or "normal operations"
            )
            return dspy.Prediction(
                zone_classification=result.zone_classification,
                access_requirements=result.access_requirements,
                screening_requirements=result.screening_requirements,
                restrictions=result.restrictions,
                answer=f"Zone: {result.zone_classification}. Access: {result.access_requirements}. {result.restrictions}"
            )

        elif query_type == "workflow_audit":
            result = self.audit_workflow(
                workflow_change=query,
                safety_context=context,
                institution_context=station_id or "general institution"
            )
            return dspy.Prediction(
                audit_result=result.audit_result,
                safety_gaps=result.safety_gaps,
                training_requirements=result.training_requirements,
                documentation_requirements=result.documentation_requirements,
                answer=f"Audit: {result.audit_result}. Gaps: {result.safety_gaps}. Training: {result.training_requirements}"
            )

        else:
            # General safety query - default to compliance check
            result = self.validate_compliance(
                proposed_action=query,
                sop_context=context,
                safety_zone_info="See SOP context for zone definitions."
            )
            return dspy.Prediction(
                answer=f"Compliance: {result.is_compliant}. {result.compliance_details}",
                is_compliant=result.is_compliant,
                safety_concerns=result.safety_concerns,
                required_personnel=result.required_personnel,
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
                "MRI safety SOPs, compliance auditing, safety zone management (Zone I-IV), "
                "minimum personnel requirements (Level 1/Level 2 MR personnel), "
                "patient screening procedures, ferromagnetic object control, "
                "quench emergency procedures, SAR monitoring, regulatory compliance, "
                "ACR appropriateness criteria review. "
                "Can consult governance_agent for institutional context or "
                "hardware_agent for technical specifications."
            ),
            available_data=context_summary
        )
