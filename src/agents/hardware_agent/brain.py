"""
Siemens Technician Brain - DSPy Signatures for Hardware Expert Agent

Defines DSPy signatures for:
- Hardware fault diagnosis
- Equipment specification lookup
- Technical troubleshooting recommendations
- Pain point analysis from questionnaire data

Domain: MR-guided radiotherapy equipment specifications and pain points
Data: Siemens questionnaire responses from healthcare institutions

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import dspy
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DiagnoseHardwareFault(dspy.Signature):
    """
    Diagnose a hardware fault based on symptom description and equipment context.

    Given a symptom report and relevant equipment specifications/pain points,
    determine:
    1. Likely root cause of the hardware issue
    2. Severity assessment
    3. Recommended diagnostic steps
    """
    symptom_description: str = dspy.InputField(
        desc="Description of the reported hardware symptom or issue"
    )
    equipment_context: str = dspy.InputField(
        desc="Relevant equipment specifications and known pain points from questionnaire data"
    )
    equipment_type: str = dspy.InputField(
        desc="Type of equipment (e.g., MR scanner, LINAC, CT simulator)"
    )

    diagnosis: str = dspy.OutputField(
        desc="Likely root cause of the hardware issue"
    )
    severity: str = dspy.OutputField(
        desc="Severity: 'low', 'medium', 'high', or 'critical'"
    )
    diagnostic_steps: str = dspy.OutputField(
        desc="Recommended diagnostic steps to confirm the issue"
    )
    requires_escalation: str = dspy.OutputField(
        desc="Whether issue requires escalation: 'yes' or 'no'"
    )


class LookupEquipmentSpec(dspy.Signature):
    """
    Lookup equipment specifications and configuration details.

    Used to answer queries about installed equipment at institutions,
    vendor information, and technical specifications.
    """
    query: str = dspy.InputField(
        desc="User's question about equipment specifications"
    )
    equipment_data: str = dspy.InputField(
        desc="Retrieved equipment data from questionnaire responses"
    )

    answer: str = dspy.OutputField(
        desc="Direct answer to the equipment specification query"
    )
    equipment_details: str = dspy.OutputField(
        desc="Detailed equipment information found"
    )
    source_institutions: str = dspy.OutputField(
        desc="Institutions referenced in the answer"
    )


class AnalyzePainPoints(dspy.Signature):
    """
    Analyze pain points reported by healthcare institutions.

    Aggregates and analyzes qualitative feedback about equipment issues,
    workflow challenges, and positioning problems.
    """
    query: str = dspy.InputField(
        desc="User's question about pain points or challenges"
    )
    pain_point_data: str = dspy.InputField(
        desc="Retrieved pain point descriptions from questionnaire data"
    )

    common_issues: str = dspy.OutputField(
        desc="Most commonly reported issues or pain points"
    )
    affected_institutions: str = dspy.OutputField(
        desc="Types of institutions most affected"
    )
    recommended_solutions: str = dspy.OutputField(
        desc="Potential solutions or mitigations for the pain points"
    )


class TroubleshootEquipment(dspy.Signature):
    """
    Provide troubleshooting guidance for equipment issues.

    Uses equipment specifications and known pain points to suggest
    troubleshooting steps for reported problems.
    """
    problem_description: str = dspy.InputField(
        desc="Description of the equipment problem"
    )
    equipment_context: str = dspy.InputField(
        desc="Equipment specifications and known issues"
    )
    institution_type: str = dspy.InputField(
        desc="Type of institution (e.g., academic, private, cancer center)"
    )

    troubleshooting_steps: str = dspy.OutputField(
        desc="Step-by-step troubleshooting guide"
    )
    likely_resolution: str = dspy.OutputField(
        desc="Most likely resolution based on similar cases"
    )
    parts_or_service_needed: str = dspy.OutputField(
        desc="Parts or service that may be required"
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
        desc="Description of this agent's domain expertise (e.g., 'MRI hardware, Siemens equipment')"
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
        desc="If redirect/consult needed: 'governance_agent', 'telemetry_agent', or 'none'"
    )
    missing_info: str = dspy.OutputField(
        desc="If partial/clarify: what information is missing or needed"
    )


class SiemensTechnicianModule(dspy.Module):
    """
    Main DSPy module for Siemens Technician agent (Hardware Agent).

    Combines multiple signatures into a cohesive hardware expert:
    1. Evaluate if request can be handled (autonomy)
    2. Diagnose hardware faults
    3. Lookup equipment specifications
    4. Analyze pain points from questionnaire data
    5. Provide troubleshooting guidance
    """

    def __init__(self):
        super().__init__()
        self.evaluate_request = dspy.ChainOfThought(EvaluateRequest)
        self.diagnose_fault = dspy.ChainOfThought(DiagnoseHardwareFault)
        self.lookup_spec = dspy.ChainOfThought(LookupEquipmentSpec)
        self.analyze_pain = dspy.ChainOfThought(AnalyzePainPoints)
        self.troubleshoot = dspy.ChainOfThought(TroubleshootEquipment)

    def forward(
        self,
        query: str,
        context: str,
        query_type: str = "general",
        equipment_type: str = "unknown"
    ) -> dspy.Prediction:
        """
        Process an incoming query through the Technician's reasoning.

        Args:
            query: User query or symptom description
            context: Retrieved equipment data and pain points
            query_type: Type of query - 'diagnosis', 'specification', 'pain_point', or 'general'
            equipment_type: Type of equipment if applicable

        Returns:
            DSPy Prediction with appropriate response based on query type
        """
        logger.info(f"Processing query (type={query_type}): {query[:100]}...")

        if query_type == "diagnosis":
            result = self.diagnose_fault(
                symptom_description=query,
                equipment_context=context,
                equipment_type=equipment_type
            )
            return dspy.Prediction(
                diagnosis=result.diagnosis,
                severity=result.severity,
                diagnostic_steps=result.diagnostic_steps,
                requires_escalation=result.requires_escalation,
                answer=f"Diagnosis: {result.diagnosis}. Severity: {result.severity}."
            )

        elif query_type == "specification":
            result = self.lookup_spec(
                query=query,
                equipment_data=context
            )
            return dspy.Prediction(
                answer=result.answer,
                equipment_details=result.equipment_details,
                source_institutions=result.source_institutions
            )

        elif query_type == "pain_point":
            result = self.analyze_pain(
                query=query,
                pain_point_data=context
            )
            return dspy.Prediction(
                answer=result.common_issues,
                common_issues=result.common_issues,
                affected_institutions=result.affected_institutions,
                recommended_solutions=result.recommended_solutions
            )

        else:
            # General query - use troubleshooting as default
            result = self.troubleshoot(
                problem_description=query,
                equipment_context=context,
                institution_type="general"
            )
            return dspy.Prediction(
                answer=result.troubleshooting_steps,
                troubleshooting_steps=result.troubleshooting_steps,
                likely_resolution=result.likely_resolution,
                parts_or_service_needed=result.parts_or_service_needed
            )

    def diagnose_hardware_issue(
        self,
        symptom: str,
        equipment_context: str,
        equipment_type: str = "MR scanner"
    ) -> dspy.Prediction:
        """
        Dedicated method for hardware fault diagnosis.

        Args:
            symptom: Description of the hardware symptom
            equipment_context: Relevant equipment data
            equipment_type: Type of equipment

        Returns:
            DSPy Prediction with diagnosis results
        """
        return self.diagnose_fault(
            symptom_description=symptom,
            equipment_context=equipment_context,
            equipment_type=equipment_type
        )

    def lookup_equipment_info(
        self,
        query: str,
        equipment_data: str
    ) -> dspy.Prediction:
        """
        Lookup equipment specifications.

        Args:
            query: Question about equipment
            equipment_data: Retrieved equipment data

        Returns:
            DSPy Prediction with equipment information
        """
        return self.lookup_spec(
            query=query,
            equipment_data=equipment_data
        )

    def analyze_institution_pain_points(
        self,
        query: str,
        pain_point_data: str
    ) -> dspy.Prediction:
        """
        Analyze pain points from questionnaire data.

        Args:
            query: Question about pain points
            pain_point_data: Retrieved pain point descriptions

        Returns:
            DSPy Prediction with pain point analysis
        """
        return self.analyze_pain(
            query=query,
            pain_point_data=pain_point_data
        )

    def evaluate_incoming_request(
        self,
        query: str,
        context_summary: str
    ) -> dspy.Prediction:
        """
        Evaluate whether this agent should handle the incoming request.

        This method enables agent autonomy by assessing:
        - Whether the query falls within hardware/equipment domain
        - Confidence level for potential response
        - Whether to redirect to or consult other agents

        Args:
            query: The incoming query or request
            context_summary: Summary of retrieved context (e.g., "Retrieved 5 equipment specs")

        Returns:
            DSPy Prediction with:
                - can_fully_answer: bool
                - confidence_level: float 0.0-1.0
                - response_type: 'answer', 'partial', 'clarify', 'redirect', 'refuse', 'consult'
                - suggested_agent: 'governance_agent', 'telemetry_agent', or 'none'
                - reasoning: explanation of decision
                - missing_info: what's missing if partial/clarify
        """
        return self.evaluate_request(
            query=query,
            my_expertise=(
                "MRI hardware, Siemens medical imaging equipment, hardware fault diagnosis, "
                "equipment specifications, MR-guided radiotherapy equipment, technical troubleshooting, "
                "Phoenix Protocol parameters, temperature sensors, thermal management. "
                "Can consult telemetry_agent for event logs or governance_agent for SLA implications."
            ),
            available_data=context_summary
        )
