"""
Diagnostic Specialist Brain - DSPy Signatures for Agent 1 (The Specialist)

Defines DSPy signatures for:
- DICOM conformance failure diagnosis (cross-ref SOP UIDs with event log errors)
- MRI hardware/software error analysis from event logs
- Technical specification lookup from DCS/CSPL documentation
- SOP Class UID cross-referencing

Domain: DICOM conformance, MRI hardware diagnostics, Siemens MRI systems
Data: DCS_MR_XA50/XA51A/XA60 PDFs, MAGNETOM SOLA CSPL, event logs (Parquet)

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import dspy
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DiagnoseDICOMFailure(dspy.Signature):
    """
    Cross-reference DICOM SOP Class UIDs from DCS PDFs with transfer failures in event logs.

    Given an error event mentioning DICOM/transfer issues and the relevant DCS conformance
    data, determine:
    1. Which SOP class or transfer syntax mismatch caused the failure
    2. The affected DICOM modality
    3. Severity and remediation steps referencing DCS documentation
    """
    error_description: str = dspy.InputField(
        desc="Error event from MRI logs mentioning DICOM, transfer, SOP, or association issues"
    )
    dcs_context: str = dspy.InputField(
        desc="Relevant DICOM conformance statement excerpts (SOP UIDs, transfer syntaxes, supported roles)"
    )
    event_log_context: str = dspy.InputField(
        desc="Related event log entries around the failure timeframe"
    )

    root_cause: str = dspy.OutputField(
        desc="Root cause: which SOP class/transfer syntax mismatch or configuration error caused the failure"
    )
    affected_modality: str = dspy.OutputField(
        desc="Affected DICOM modality or service (e.g., MR Image Storage, Worklist, Print)"
    )
    severity: str = dspy.OutputField(
        desc="Severity: 'low', 'medium', 'high', or 'critical'"
    )
    remediation: str = dspy.OutputField(
        desc="Specific remediation steps referencing DCS documentation sections"
    )


class AnalyzeHardwareError(dspy.Signature):
    """
    Diagnose MRI hardware/software errors from event logs using technical documentation.

    Given a cluster of related error events and relevant hardware specifications,
    determine the technical diagnosis and whether field service is needed.
    """
    error_events: str = dspy.InputField(
        desc="Cluster of related error events from MRI system logs (source, event_id, description, occurrence_count)"
    )
    technical_context: str = dspy.InputField(
        desc="Relevant hardware specs, DCS data, and known failure modes"
    )
    scanner_model: str = dspy.InputField(
        desc="MRI scanner model (e.g., MAGNETOM Sola, XA50, XA60)"
    )

    diagnosis: str = dspy.OutputField(
        desc="Technical diagnosis of the hardware/software issue"
    )
    affected_component: str = dspy.OutputField(
        desc="Affected system component (gradient coils, RF amplifier, cooling, cryogen, software, network)"
    )
    severity: str = dspy.OutputField(
        desc="Severity: 'low', 'medium', 'high', or 'critical'"
    )
    diagnostic_steps: str = dspy.OutputField(
        desc="Step-by-step diagnostic verification procedure"
    )
    requires_service: str = dspy.OutputField(
        desc="'yes' or 'no' - whether Siemens field service intervention is needed"
    )


class LookupTechnicalSpec(dspy.Signature):
    """
    Look up MRI technical specifications from DCS and hardware documentation.

    Used to answer queries about DICOM support, scanner capabilities,
    transfer syntaxes, and system specifications.
    """
    query: str = dspy.InputField(
        desc="Technical query about MRI specifications, DICOM support, or scanner capabilities"
    )
    documentation_context: str = dspy.InputField(
        desc="Retrieved DCS/CSPL documentation excerpts"
    )

    answer: str = dspy.OutputField(
        desc="Technical answer with specific values, parameters, or UIDs"
    )
    source_document: str = dspy.OutputField(
        desc="Source document and section referenced (e.g., 'DCS_MR_XA60, Section 4.2')"
    )
    confidence: str = dspy.OutputField(
        desc="Confidence level: 'high', 'medium', or 'low'"
    )


class CrossReferenceSOP(dspy.Signature):
    """
    Cross-reference SOP Class UIDs from event log errors with DCS support tables.

    Determines if a SOP Class UID involved in a failure is supported by the scanner,
    and identifies any mismatch in transfer syntax or role.
    """
    sop_uid: str = dspy.InputField(
        desc="DICOM SOP Class UID from the error event or query"
    )
    dcs_sop_table: str = dspy.InputField(
        desc="SOP class support table from the relevant DCS PDF"
    )
    error_context: str = dspy.InputField(
        desc="Full error context from event logs if available"
    )

    is_supported: str = dspy.OutputField(
        desc="'yes', 'no', or 'partial' - whether the SOP class is supported by this scanner"
    )
    mismatch_details: str = dspy.OutputField(
        desc="Details of any SOP/transfer syntax/role mismatch found"
    )
    recommendation: str = dspy.OutputField(
        desc="Recommended fix, workaround, or configuration change"
    )


class AnalyzeEventLogs(dspy.Signature):
    """
    Analyze MRI event log data retrieved via Polars from per-customer Parquet files.

    Given pre-filtered event log data (errors, warnings, DICOM events),
    identify patterns, recurring issues, and correlations with known failure modes.
    """
    customer_id: str = dspy.InputField(
        desc="Siemens customer ID (e.g., 'mr200103')"
    )
    event_data_summary: str = dspy.InputField(
        desc="Summary of event log data: top errors, temporal patterns, source distribution"
    )
    known_failure_modes: str = dspy.InputField(
        desc="Relevant failure modes from the curated FM catalog (FM-001 to FM-020)"
    )

    analysis: str = dspy.OutputField(
        desc="Analysis of event log patterns and their operational significance"
    )
    identified_issues: str = dspy.OutputField(
        desc="List of identified issues with severity and frequency"
    )
    failure_mode_matches: str = dspy.OutputField(
        desc="Which known failure modes (FM-XXX) match the observed patterns"
    )
    recommendations: str = dspy.OutputField(
        desc="Recommended actions based on event log analysis"
    )


class AnswerGeneralQuery(dspy.Signature):
    """You are The Specialist — a senior Siemens MRI field service engineer and DICOM conformance
expert with deep knowledge of MAGNETOM MRI systems.

Your expertise includes:
- Siemens MAGNETOM scanner platforms (Sola, Vida, Altea, Free.Max) running syngo MR XA50,
  XA51A, and XA60 software
- DICOM Conformance Statements (DCS): SOP Class UIDs, transfer syntaxes, DIMSE services,
  association negotiation, Storage Commitment, MPPS, Modality Worklist
- MRI hardware subsystems: gradient coils, RF amplifiers, cryogen/helium systems, thermal
  management, patient table, bore components
- Event log analysis: error codes, warning patterns, source identification (MARS, MeasServer,
  XA Host, DICOM services)
- Known failure modes (FM-001 to FM-020): gradient thermal events, RF amplifier faults,
  cryogen pressure anomalies, helium boil-off, software crashes, PACS transfer failures
- CSPL (Clinical Software Package List) capabilities per software version
- Preventive maintenance schedules and field service intervention criteria

When diagnosing issues, follow a structured approach:
1. Identify the affected subsystem from error patterns
2. Cross-reference with known failure modes (FM catalog)
3. Check DCS conformance if DICOM-related
4. Assess severity and whether field service intervention is needed
5. Provide specific remediation steps referencing documentation

Always cite specific DCS sections, failure mode IDs, or event log patterns when available."""
    query: str = dspy.InputField(desc="User question about MRI hardware, DICOM, or technical diagnostics")
    context: str = dspy.InputField(desc="Retrieved documentation and data relevant to the query")

    answer: str = dspy.OutputField(desc="Comprehensive, expert-level answer grounded in the provided context")
    confidence: str = dspy.OutputField(desc="'high', 'medium', or 'low' based on context relevance")
    sources_used: str = dspy.OutputField(desc="Which context documents were most relevant")
    follow_up: str = dspy.OutputField(desc="Suggested follow-up questions or actions")


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
        desc="If redirect/consult needed: 'governance_agent', 'telemetry_agent', or 'none'"
    )
    missing_info: str = dspy.OutputField(
        desc="If partial/clarify: what information is missing or needed"
    )


class DiagnosticSpecialistModule(dspy.Module):
    """
    Main DSPy module for The Specialist (Agent 1 - Diagnostic & Technical).

    Combines multiple signatures into a cohesive diagnostic expert:
    1. Evaluate if request can be handled (autonomy)
    2. Diagnose DICOM transfer failures by cross-referencing DCS data
    3. Analyze hardware/software errors from event logs
    4. Look up technical specifications
    5. Cross-reference SOP Class UIDs
    """

    def __init__(self, router_lm=None):
        super().__init__()
        self.router_lm = router_lm
        self.evaluate_request = dspy.ChainOfThought(EvaluateRequest)
        self.diagnose_dicom = dspy.ChainOfThought(DiagnoseDICOMFailure)
        self.analyze_hardware = dspy.ChainOfThought(AnalyzeHardwareError)
        self.lookup_spec = dspy.ChainOfThought(LookupTechnicalSpec)
        self.cross_reference = dspy.ChainOfThought(CrossReferenceSOP)
        self.analyze_event_logs = dspy.ChainOfThought(AnalyzeEventLogs)
        self.answer_general = dspy.ChainOfThought(AnswerGeneralQuery)

    def forward(
        self,
        query: str,
        context: str,
        query_type: str = "general",
        equipment_type: str = "MRI",
        event_log_context: str = ""
    ) -> dspy.Prediction:
        """
        Process an incoming query through the Specialist's reasoning.

        Args:
            query: User query or error description
            context: Retrieved DCS/technical documentation and event log data
            query_type: 'dicom_diagnosis', 'hardware_error', 'technical_spec', or 'general'
            equipment_type: Scanner model if known
            event_log_context: Real event log data if available

        Returns:
            DSPy Prediction with appropriate response based on query type
        """
        logger.info(f"Processing query (type={query_type}): {query[:100]}...")

        if query_type == "dicom_diagnosis":
            result = self.diagnose_dicom(
                error_description=query,
                dcs_context=context,
                event_log_context=event_log_context or "No event log data available for this query."
            )
            return dspy.Prediction(
                diagnosis=result.root_cause,
                severity=result.severity,
                affected_component=result.affected_modality,
                diagnostic_steps=result.remediation,
                answer=f"DICOM Diagnosis: {result.root_cause}. Severity: {result.severity}. Fix: {result.remediation}"
            )

        elif query_type == "hardware_error":
            result = self.analyze_hardware(
                error_events=query,
                technical_context=context,
                scanner_model=equipment_type
            )
            return dspy.Prediction(
                diagnosis=result.diagnosis,
                severity=result.severity,
                affected_component=result.affected_component,
                diagnostic_steps=result.diagnostic_steps,
                requires_service=result.requires_service,
                answer=f"Hardware Diagnosis: {result.diagnosis}. Component: {result.affected_component}. Severity: {result.severity}."
            )

        elif query_type == "technical_spec":
            result = self.lookup_spec(
                query=query,
                documentation_context=context
            )
            return dspy.Prediction(
                answer=result.answer,
                source_document=result.source_document,
                confidence=result.confidence
            )

        else:
            # General query - use flexible Q&A signature
            result = self.answer_general(query=query, context=context)
            return dspy.Prediction(
                answer=result.answer,
                confidence=result.confidence,
                sources_used=result.sources_used,
                follow_up=result.follow_up,
            )

    def evaluate_incoming_request(
        self,
        query: str,
        context_summary: str
    ) -> dspy.Prediction:
        """
        Evaluate whether this agent should handle the incoming request.

        Args:
            query: The incoming query or request
            context_summary: Summary of retrieved context

        Returns:
            DSPy Prediction with autonomy evaluation
        """
        return self.evaluate_request(
            query=query,
            my_expertise=(
                "DICOM conformance analysis, MRI hardware diagnostics, SOP Class UID analysis, "
                "transfer syntax matching, Siemens MRI systems (XA50/XA51A/XA60, MAGNETOM Sola), "
                "event log error diagnosis, gradient coils, RF amplifiers, cryogen systems, "
                "thermal management, software service crashes, PACS/DICOM transfer failures. "
                "Can consult governance_agent for institutional context or telemetry_agent for safety compliance."
            ),
            available_data=context_summary
        )
