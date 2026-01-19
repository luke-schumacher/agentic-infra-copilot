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


class SiemensTechnicianModule(dspy.Module):
    """
    Main DSPy module for Siemens Technician agent.

    Combines multiple signatures into a cohesive hardware expert:
    1. Diagnose hardware faults
    2. Lookup equipment specifications
    3. Analyze pain points from questionnaire data
    4. Provide troubleshooting guidance
    """

    def __init__(self):
        super().__init__()
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
