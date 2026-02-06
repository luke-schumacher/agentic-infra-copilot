"""
Emergence Test Cases - Ablation Testing Framework

Defines test case structures for validating emergence in the MAS.
Each test case includes what single agents see and conclude alone,
plus the expected emergent diagnosis that only MAS should achieve.

Per design doc section 5 - Emergence Test Cases.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Difficulty(str, Enum):
    """Test case difficulty levels."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class EmergenceTestCase(BaseModel):
    """
    Test case structure for ablation testing.

    Each test case defines:
    - What each agent sees in isolation
    - What each agent concludes alone (should be incomplete/wrong)
    - The correct integrated answer (only MAS should get this)
    """
    name: str = Field(description="Test case identifier")
    description: str = Field(description="Description of the scenario")

    # What each agent sees in isolation
    governance_context: str = Field(
        description="SLA data, policy docs - what Governance Agent sees"
    )
    hardware_context: str = Field(
        description="Equipment records, specs - what Hardware Agent sees"
    )
    telemetry_context: str = Field(
        description="Event logs, metrics - what Telemetry Agent sees"
    )

    # What each agent concludes alone (should be incomplete/wrong)
    governance_alone: str = Field(
        description="What Governance concludes without other agents"
    )
    hardware_alone: str = Field(
        description="What Hardware concludes without other agents"
    )
    telemetry_alone: str = Field(
        description="What Telemetry concludes without other agents"
    )

    # The correct integrated answer (only MAS gets this)
    emergent_diagnosis: str = Field(
        description="The real root cause that requires cross-domain synthesis"
    )
    reasoning_chain: List[str] = Field(
        description="How agents should build on each other to reach diagnosis"
    )

    # Evaluation criteria
    requires_cross_domain: bool = Field(
        default=True,
        description="True = only MAS can solve this correctly"
    )
    difficulty: Difficulty = Field(
        default=Difficulty.MODERATE,
        description="Test difficulty: simple, moderate, complex"
    )

    # Ground truth for automated scoring
    required_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords that must appear in correct diagnosis"
    )
    expected_agent_sequence: List[str] = Field(
        default_factory=list,
        description="Expected order of agent consultations"
    )

    # Metadata
    domain: str = Field(
        default="healthcare",
        description="Domain context for the test"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for filtering tests"
    )


class EmergenceTestSuite(BaseModel):
    """Collection of emergence test cases."""
    name: str
    description: str
    test_cases: List[EmergenceTestCase]

    def get_by_difficulty(self, difficulty: Difficulty) -> List[EmergenceTestCase]:
        """Filter test cases by difficulty."""
        return [tc for tc in self.test_cases if tc.difficulty == difficulty]

    def get_by_tag(self, tag: str) -> List[EmergenceTestCase]:
        """Filter test cases by tag."""
        return [tc for tc in self.test_cases if tag in tc.tags]


# Pre-defined test cases from design doc
CASCADING_THERMAL_FAULT = EmergenceTestCase(
    name="cascading_thermal_fault",
    description="Thermal sensor calibration causes 90-minute failure cycle",
    governance_context=(
        "Uptime SLA breached: 94% vs 99% target. "
        "Vendor penalty clause may apply. "
        "Monthly SLA report shows degradation over past 2 weeks."
    ),
    hardware_context=(
        "Temperature sensor shows intermittent readings. "
        "Sensor last calibrated 6 months ago. "
        "Thermal management system logs show periodic shutdowns. "
        "Sensor model: Siemens TempGuard-X3."
    ),
    telemetry_context=(
        "Session failures every 90 minutes. "
        "Pattern consistent across past 14 days. "
        "Thermal shutdown events correlate with failure timestamps. "
        "Average session duration before failure: 85-92 minutes."
    ),
    governance_alone=(
        "SLA breach detected. Recommend initiating vendor penalty clause. "
        "Root cause: vendor service level failure."
    ),
    hardware_alone=(
        "Temperature sensor showing drift. Recommend sensor replacement. "
        "Root cause: faulty sensor hardware."
    ),
    telemetry_alone=(
        "Session failures following 90-minute pattern. "
        "Recommend increasing session timeout threshold. "
        "Root cause: software timeout configuration."
    ),
    emergent_diagnosis=(
        "Intermittent temperature sensor triggers thermal safety shutdown every 90 minutes, "
        "causing session drops and SLA breach. Root cause: sensor calibration drift, "
        "not vendor SLA failure or software configuration. "
        "Recommended action: Recalibrate sensor, not replace. "
        "SLA penalty should be waived as root cause is internal calibration issue."
    ),
    reasoning_chain=[
        "Telemetry: '90-minute pattern exists in session failures'",
        "Hardware: 'Thermal cycle matches the 90-minute pattern, sensor shows drift'",
        "Governance: 'Root cause is hardware calibration, not vendor SLA. Penalty waived.'"
    ],
    requires_cross_domain=True,
    difficulty=Difficulty.MODERATE,
    required_keywords=["calibration", "sensor", "90", "thermal", "waive"],
    expected_agent_sequence=["governance_agent", "telemetry_agent", "hardware_agent"],
    domain="healthcare",
    tags=["thermal", "mri", "sla", "sensor"]
)


PHANTOM_LOAD_SPIKE = EmergenceTestCase(
    name="phantom_load_spike",
    description="Apparent overload caused by monitoring artifact, not real load",
    governance_context=(
        "Energy consumption SLA shows 15% overage for the month. "
        "Budget alert triggered. Cost optimization review required."
    ),
    hardware_context=(
        "Power meter readings nominal. "
        "No equipment changes in past month. "
        "Calibration certificates current."
    ),
    telemetry_context=(
        "Load monitoring system shows spikes during off-hours. "
        "Spikes correlate with backup job schedule. "
        "Network latency to monitoring server increased recently."
    ),
    governance_alone=(
        "Energy SLA breach. Recommend equipment audit and usage review. "
        "Possible unauthorized after-hours usage."
    ),
    hardware_alone=(
        "Equipment functioning normally. Power readings within spec. "
        "No hardware issue detected."
    ),
    telemetry_alone=(
        "Load spikes detected during backup windows. "
        "Possible interaction with backup system."
    ),
    emergent_diagnosis=(
        "Load spikes are monitoring artifacts caused by network latency during backup jobs. "
        "Power meters show actual consumption is normal. "
        "The monitoring system aggregates delayed readings, creating apparent spikes. "
        "No actual energy overuse - SLA breach is false positive."
    ),
    reasoning_chain=[
        "Governance: 'Energy SLA breach detected'",
        "Hardware: 'But actual power readings are normal'",
        "Telemetry: 'Spikes correlate with backup schedule and network latency'",
        "Synthesis: 'Monitoring artifact, not real overload'"
    ],
    requires_cross_domain=True,
    difficulty=Difficulty.COMPLEX,
    required_keywords=["monitoring", "artifact", "backup", "latency", "false"],
    expected_agent_sequence=["governance_agent", "hardware_agent", "telemetry_agent"],
    domain="healthcare",
    tags=["monitoring", "false_positive", "energy"]
)


GRADIENT_COIL_DEGRADATION = EmergenceTestCase(
    name="gradient_coil_degradation",
    description="Subtle image quality degradation from coil aging",
    governance_context=(
        "Image quality complaints from radiologists increasing. "
        "Patient throughput down 8% this quarter. "
        "No SLA breach yet but trending toward threshold."
    ),
    hardware_context=(
        "Gradient coil age: 7 years (expected life: 8-10 years). "
        "Last maintenance: 3 months ago, passed all checks. "
        "Manufacturer advisory notes early degradation patterns."
    ),
    telemetry_context=(
        "Scan duration increasing slightly (2-3% longer per scan). "
        "Error rate normal. No faults logged. "
        "Subtle increase in image reconstruction time."
    ),
    governance_alone=(
        "Throughput declining, investigate scheduling or staffing. "
        "No equipment issue flagged."
    ),
    hardware_alone=(
        "Equipment passed maintenance. Coil within expected life. "
        "No immediate action needed."
    ),
    telemetry_alone=(
        "Slight performance degradation but within tolerance. "
        "Continue monitoring."
    ),
    emergent_diagnosis=(
        "Gradient coil showing early degradation consistent with end-of-life patterns. "
        "2-3% scan time increase plus image quality complaints indicate coil aging. "
        "Recommend proactive replacement planning before SLA breach. "
        "Schedule manufacturer inspection within 30 days."
    ),
    reasoning_chain=[
        "Governance: 'Quality complaints and throughput decline'",
        "Telemetry: 'Subtle timing increase correlates with complaints'",
        "Hardware: 'Coil age plus manufacturer advisory explains pattern'",
        "Synthesis: 'Proactive coil replacement needed'"
    ],
    requires_cross_domain=True,
    difficulty=Difficulty.COMPLEX,
    required_keywords=["gradient", "coil", "degradation", "proactive", "replacement"],
    expected_agent_sequence=["governance_agent", "telemetry_agent", "hardware_agent"],
    domain="healthcare",
    tags=["mri", "coil", "degradation", "proactive"]
)


HELIUM_BOILOFF_CASCADE = EmergenceTestCase(
    name="helium_boiloff_cascade",
    description="Helium level drop causes scan aborts and SLA breach",
    governance_context=(
        "Scan completion SLA at 88% vs 95% target for past week. "
        "Three patient reschedules due to scanner downtime. "
        "Vendor maintenance contract requires 48h response."
    ),
    hardware_context=(
        "Cold head compressor running 20% longer cycles than normal. "
        "Helium level at 62% (threshold: 60% triggers quench protection). "
        "Last helium refill: 8 months ago. Typical interval: 12 months."
    ),
    telemetry_context=(
        "Scan abort events increasing: 3 per day vs normal 0.2 per day. "
        "Aborts correlate with magnet room temperature spikes. "
        "Compressor alarm events logged at 2am and 4am daily."
    ),
    governance_alone=(
        "SLA breach requires vendor escalation under maintenance contract. "
        "Recommend patient rescheduling protocol."
    ),
    hardware_alone=(
        "Helium level low but above quench threshold. "
        "Schedule routine helium refill within standard maintenance window."
    ),
    telemetry_alone=(
        "Scan abort rate elevated. Possible software or sequence issue. "
        "Recommend scanner restart and sequence parameter review."
    ),
    emergent_diagnosis=(
        "Accelerated helium boil-off from cold head compressor degradation. "
        "Compressor running extended cycles indicates reduced cooling capacity, "
        "causing helium loss 50% faster than normal. Scan aborts are triggered "
        "by magnet instability as helium approaches critical level. "
        "Emergency: schedule helium refill AND cold head service before quench. "
        "Vendor 48h response clause should be invoked immediately."
    ),
    reasoning_chain=[
        "Telemetry: 'Scan aborts correlate with temperature spikes and compressor alarms'",
        "Hardware: 'Compressor running long cycles = degraded cooling, accelerating helium loss'",
        "Governance: 'Invoke 48h vendor response clause before quench occurs'"
    ],
    requires_cross_domain=True,
    difficulty=Difficulty.COMPLEX,
    required_keywords=["helium", "compressor", "boil-off", "quench", "48h"],
    expected_agent_sequence=["governance_agent", "telemetry_agent", "hardware_agent"],
    domain="healthcare",
    tags=["mri", "cryogenic", "helium", "compressor", "sla"]
)


SOFTWARE_UPDATE_REGRESSION = EmergenceTestCase(
    name="software_update_regression",
    description="Software update causes subtle timing regression affecting throughput",
    governance_context=(
        "Patient throughput down 12% since last week. "
        "No staffing changes. No scheduling modifications. "
        "Revenue impact estimated at significant for the quarter."
    ),
    hardware_context=(
        "Software update applied 8 days ago: syngo XA60 patch 3.2. "
        "All hardware diagnostics pass. No component changes. "
        "Manufacturer release notes mention 'improved reconstruction pipeline'."
    ),
    telemetry_context=(
        "Average scan duration increased by 15-20 seconds per sequence. "
        "Reconstruction time increased 40% across all protocols. "
        "No error events logged. All scans completing successfully."
    ),
    governance_alone=(
        "Throughput decline requires operational review. "
        "Consider scheduling optimization or staffing adjustments."
    ),
    hardware_alone=(
        "All hardware passing diagnostics. Software update applied recently "
        "but release notes indicate improvement, not degradation."
    ),
    telemetry_alone=(
        "Scan and reconstruction times increased. Performance degradation "
        "detected but no errors. Possible resource contention."
    ),
    emergent_diagnosis=(
        "syngo XA60 patch 3.2 introduced a reconstruction pipeline regression. "
        "The 'improved' pipeline actually increases processing time by 40%, "
        "adding 15-20 seconds per scan and causing the 12% throughput drop. "
        "Recommend: rollback to patch 3.1, report regression to Siemens, "
        "and request hotfix. Throughput SLA breach is software-caused."
    ),
    reasoning_chain=[
        "Governance: 'Throughput dropped 12% with no operational changes'",
        "Telemetry: 'Reconstruction time up 40% since specific date'",
        "Hardware: 'Software patch applied on that exact date'",
        "Synthesis: 'Patch 3.2 regression caused throughput drop'"
    ],
    requires_cross_domain=True,
    difficulty=Difficulty.MODERATE,
    required_keywords=["patch", "reconstruction", "regression", "rollback", "throughput"],
    expected_agent_sequence=["governance_agent", "telemetry_agent", "hardware_agent"],
    domain="healthcare",
    tags=["mri", "software", "regression", "throughput"]
)


RF_AMPLIFIER_INTERMITTENT = EmergenceTestCase(
    name="rf_amplifier_intermittent",
    description="Intermittent RF amplifier causes image quality complaints and repeat scans",
    governance_context=(
        "Radiologist complaints about image quality increasing. "
        "Repeat scan rate up from 3% to 11% this month. "
        "No formal SLA breach yet but patient satisfaction declining."
    ),
    hardware_context=(
        "RF amplifier tube age: 4.5 years (rated life: 5 years). "
        "Last calibration: 2 months ago, passed. "
        "Power output measurements show 3% variance (spec: <1%)."
    ),
    telemetry_context=(
        "Signal-to-noise ratio fluctuating on T1-weighted sequences. "
        "No consistent pattern - failures appear random. "
        "Approximately 8-10% of scans show brightness artifacts."
    ),
    governance_alone=(
        "Image quality complaints require radiologist feedback session. "
        "Review scan protocols and technologist training."
    ),
    hardware_alone=(
        "RF amplifier approaching end of life but still within calibration. "
        "Monitor power output variance."
    ),
    telemetry_alone=(
        "SNR fluctuations detected but random - no clear pattern. "
        "Possible coil positioning issue or patient-dependent factor."
    ),
    emergent_diagnosis=(
        "RF amplifier tube intermittent failure due to end-of-life thermal fatigue. "
        "3% power variance causes random SNR fluctuations and brightness artifacts, "
        "leading to 11% repeat scan rate and radiologist complaints. "
        "Failure is intermittent because tube performance degrades under thermal load "
        "and recovers when cool. Recommend proactive tube replacement before complete failure. "
        "This is hardware degradation, not protocol or technologist issue."
    ),
    reasoning_chain=[
        "Governance: 'Repeat scan rate tripled, quality complaints rising'",
        "Telemetry: 'Random SNR fluctuations and brightness artifacts on 8-10% of scans'",
        "Hardware: 'RF tube at 90% of rated life with 3x normal power variance'",
        "Synthesis: 'Intermittent tube failure causing random quality issues'"
    ],
    requires_cross_domain=True,
    difficulty=Difficulty.MODERATE,
    required_keywords=["rf", "amplifier", "tube", "intermittent", "replacement"],
    expected_agent_sequence=["governance_agent", "telemetry_agent", "hardware_agent"],
    domain="healthcare",
    tags=["mri", "rf", "image_quality", "amplifier"]
)


MISSED_MAINTENANCE_ESCALATION = EmergenceTestCase(
    name="missed_maintenance_escalation",
    description="Missed preventive maintenance leads to cascading component issues",
    governance_context=(
        "Quarterly preventive maintenance was postponed twice due to scheduling conflicts. "
        "Now 6 months overdue. Maintenance SLA requires quarterly service. "
        "Insurance compliance requires documented maintenance schedule."
    ),
    hardware_context=(
        "Gradient coil cooling water filter shows reduced flow rate. "
        "Bore ventilation filters visibly dirty. "
        "Table rail lubrication overdue - slight positioning noise."
    ),
    telemetry_context=(
        "Gradient system temperature trending upward over 3 months. "
        "Table positioning time increased by 2 seconds. "
        "No hard faults but multiple yellow-level warnings increasing."
    ),
    governance_alone=(
        "Maintenance SLA violated. Schedule immediate maintenance visit. "
        "Document deviation for insurance compliance."
    ),
    hardware_alone=(
        "Multiple minor issues: filter, ventilation, lubrication. "
        "Each individually low-severity. Standard maintenance items."
    ),
    telemetry_alone=(
        "Gradual performance degradation across multiple subsystems. "
        "No single critical fault. Continue monitoring."
    ),
    emergent_diagnosis=(
        "Missed preventive maintenance has created compounding degradation: "
        "dirty cooling filter increases gradient temperature, dirty bore filters "
        "reduce patient comfort, unlubricated table adds positioning time. "
        "Together these reduce throughput, risk gradient thermal protection trips, "
        "and violate maintenance SLA and insurance compliance. "
        "Priority: emergency maintenance visit addressing all items. "
        "Document root cause as scheduling failure, not equipment failure."
    ),
    reasoning_chain=[
        "Governance: 'Maintenance 6 months overdue, SLA and insurance at risk'",
        "Hardware: 'Multiple minor issues all traceable to skipped maintenance'",
        "Telemetry: 'Gradual degradation trending across subsystems'",
        "Synthesis: 'Compounding maintenance debt, not equipment failure'"
    ],
    requires_cross_domain=True,
    difficulty=Difficulty.SIMPLE,
    required_keywords=["maintenance", "overdue", "compounding", "scheduling", "compliance"],
    expected_agent_sequence=["governance_agent", "hardware_agent", "telemetry_agent"],
    domain="healthcare",
    tags=["mri", "maintenance", "preventive", "compliance"]
)


NETWORK_FALSE_ALARM = EmergenceTestCase(
    name="network_false_alarm",
    description="Network drops cause missed telemetry creating false equipment alarm",
    governance_context=(
        "Equipment availability dashboard shows scanner offline 3 times this week. "
        "Each 'outage' lasted 5-15 minutes. Uptime SLA at risk."
    ),
    hardware_context=(
        "Scanner hardware all functional. No reboot events. "
        "Network switch in equipment room replaced 2 weeks ago. "
        "New switch firmware has known issue with VLAN tagging."
    ),
    telemetry_context=(
        "Telemetry heartbeat gaps of 5-15 minutes detected. "
        "No equipment error events during gap periods. "
        "Gaps correlate with IT department backup window."
    ),
    governance_alone=(
        "Scanner showing intermittent outages. Investigate hardware reliability. "
        "May need vendor service call."
    ),
    hardware_alone=(
        "Scanner hardware healthy. New network switch installed recently. "
        "No hardware issues detected."
    ),
    telemetry_alone=(
        "Heartbeat gaps during backup windows. "
        "Possible network congestion during backups."
    ),
    emergent_diagnosis=(
        "False scanner outage alarms caused by network switch firmware bug. "
        "New switch drops VLAN-tagged monitoring packets during high traffic "
        "(backup windows), causing telemetry gaps that appear as outages. "
        "Scanner was operational throughout - no actual downtime. "
        "Fix: update switch firmware or configure QoS for monitoring traffic. "
        "SLA should not count these as real outages."
    ),
    reasoning_chain=[
        "Governance: 'Dashboard shows outages, SLA at risk'",
        "Telemetry: 'Gaps correlate with backup windows, no equipment errors'",
        "Hardware: 'Network switch firmware has known VLAN bug'",
        "Synthesis: 'False alarms from network issue, not equipment issue'"
    ],
    requires_cross_domain=True,
    difficulty=Difficulty.MODERATE,
    required_keywords=["network", "switch", "firmware", "false", "vlan"],
    expected_agent_sequence=["governance_agent", "telemetry_agent", "hardware_agent"],
    domain="healthcare",
    tags=["mri", "network", "false_alarm", "monitoring"]
)


PROTOCOL_CONFLICT_SLA = EmergenceTestCase(
    name="protocol_conflict_sla",
    description="Protocol parameter conflict causes scan failures during specific exams",
    governance_context=(
        "Cardiac MRI completion rate dropped to 75% (target: 95%). "
        "Affected only cardiac protocols - other modalities normal. "
        "Cardiologist requesting alternate imaging arrangements."
    ),
    hardware_context=(
        "ECG gating module recently updated with new firmware. "
        "New firmware changes default trigger sensitivity. "
        "Dot Cockpit protocol database synced after update."
    ),
    telemetry_context=(
        "Cardiac-gated sequences failing with 'irregular trigger' errors. "
        "Error rate: 25% of cardiac scans. "
        "Non-gated sequences performing normally."
    ),
    governance_alone=(
        "Cardiac MRI SLA breached. Arrange backup cardiac imaging "
        "and escalate to radiology leadership."
    ),
    hardware_alone=(
        "ECG module firmware updated. New defaults may need adjustment. "
        "Recommend reviewing trigger parameters."
    ),
    telemetry_alone=(
        "Gating errors on cardiac sequences. "
        "Possible patient lead placement or ECG signal quality issue."
    ),
    emergent_diagnosis=(
        "ECG gating firmware update changed default trigger sensitivity, "
        "which conflicts with existing cardiac protocol parameters in Dot Cockpit. "
        "The new sensitivity threshold rejects normal R-wave triggers that "
        "previously worked. Fix: update cardiac protocol trigger thresholds "
        "in Dot Cockpit to match new firmware defaults. "
        "This is a protocol-firmware mismatch, not patient or hardware issue. "
        "Cardiac SLA will recover immediately after parameter correction."
    ),
    reasoning_chain=[
        "Governance: 'Only cardiac protocols affected, started recently'",
        "Telemetry: 'Gating trigger errors on 25% of cardiac scans'",
        "Hardware: 'ECG firmware update changed default trigger sensitivity'",
        "Synthesis: 'Firmware-protocol parameter mismatch'"
    ],
    requires_cross_domain=True,
    difficulty=Difficulty.MODERATE,
    required_keywords=["gating", "firmware", "trigger", "protocol", "cardiac"],
    expected_agent_sequence=["governance_agent", "telemetry_agent", "hardware_agent"],
    domain="healthcare",
    tags=["mri", "cardiac", "protocol", "firmware", "gating"]
)


KNOWN_FAULT_CODE_LOOKUP = EmergenceTestCase(
    name="known_fault_code_lookup",
    description="Known fault code with straightforward resolution",
    governance_context=(
        "No SLA breach reported. Single incident logged for documentation."
    ),
    hardware_context=(
        "Bore ventilation fan RPM dropped to zero. "
        "Fan motor model: standard replacement part. "
        "Last replaced: 3 years ago."
    ),
    telemetry_context=(
        "Bore temperature sensor shows gradual rise. "
        "Fan failure event logged 2 hours ago. "
        "No impact on scan quality yet."
    ),
    governance_alone=(
        "No SLA breach. Log the incident for maintenance tracking."
    ),
    hardware_alone=(
        "Fan motor failure. Order replacement part and schedule repair."
    ),
    telemetry_alone=(
        "Bore temperature rising but within safe limits for now. "
        "Monitor closely."
    ),
    emergent_diagnosis=(
        "Bore ventilation fan motor failure (FM-012). Standard component failure "
        "with straightforward replacement. Currently no impact on scanning but "
        "bore temperature will continue to rise. Schedule repair within 24 hours "
        "to avoid patient comfort issues. No SLA impact if resolved promptly."
    ),
    reasoning_chain=[
        "Hardware: 'Fan motor failure, standard replacement'",
        "Telemetry: 'Temperature rising, confirms fan down'",
        "Governance: 'No SLA breach if resolved within 24h'"
    ],
    requires_cross_domain=False,
    difficulty=Difficulty.SIMPLE,
    required_keywords=["fan", "motor", "replacement", "temperature", "24"],
    expected_agent_sequence=["governance_agent", "hardware_agent", "telemetry_agent"],
    domain="healthcare",
    tags=["mri", "ventilation", "simple", "maintenance"]
)


SHIMMING_ENVIRONMENTAL = EmergenceTestCase(
    name="shimming_environmental",
    description="Environmental change causes shimming failures on specific body regions",
    governance_context=(
        "Abdominal MRI image quality complaints from radiologists. "
        "Fat-water swap artifacts appearing in liver studies. "
        "Other body regions unaffected."
    ),
    hardware_context=(
        "Building construction started on adjacent floor 3 weeks ago. "
        "New elevator installation involves steel beams. "
        "Shim system calibration was nominal at last check (2 months ago)."
    ),
    telemetry_context=(
        "Auto-shim failures increasing on large FOV abdominal scans. "
        "B0 field map shows new asymmetric distortion pattern. "
        "Small FOV brain scans shimming normally."
    ),
    governance_alone=(
        "Abdominal scan quality degraded. Review protocols and "
        "consider referral to alternate facility."
    ),
    hardware_alone=(
        "Construction nearby may introduce ferromagnetic interference. "
        "Shim system may need recalibration."
    ),
    telemetry_alone=(
        "Auto-shim failures on large FOV only. "
        "New distortion pattern suggests external magnetic interference."
    ),
    emergent_diagnosis=(
        "Adjacent construction (elevator steel beams) introduced ferromagnetic "
        "interference affecting B0 homogeneity. Only large FOV abdominal scans "
        "are affected because they are more sensitive to field distortion at the "
        "edges. Recommend: immediate shim recalibration, request construction "
        "schedule for coordinating re-shims, and consider temporary protocol "
        "adjustments (reduced FOV with multiple acquisitions) until construction complete."
    ),
    reasoning_chain=[
        "Governance: 'Only abdominal scans affected, started 3 weeks ago'",
        "Hardware: 'Construction with steel beams started 3 weeks ago'",
        "Telemetry: 'New asymmetric B0 distortion on large FOV only'",
        "Synthesis: 'Construction ferromagnetic interference'"
    ],
    requires_cross_domain=True,
    difficulty=Difficulty.COMPLEX,
    required_keywords=["construction", "ferromagnetic", "shimming", "B0", "FOV"],
    expected_agent_sequence=["governance_agent", "telemetry_agent", "hardware_agent"],
    domain="healthcare",
    tags=["mri", "shimming", "environment", "interference"]
)


MULTI_SCANNER_COOLING = EmergenceTestCase(
    name="multi_scanner_cooling",
    description="Shared cooling system failure causes staggered failures across scanners",
    governance_context=(
        "Two MRI scanners both showing reduced uptime this week. "
        "Combined availability at 85% vs 99% SLA each. "
        "Unusual: both scanners rarely fail simultaneously."
    ),
    hardware_context=(
        "Both scanners share a building chilled water loop for cooling. "
        "Chiller capacity was recently reduced for energy savings. "
        "Each scanner's internal cooling appears functional."
    ),
    telemetry_context=(
        "Scanner A thermal shutdowns in morning hours. "
        "Scanner B thermal shutdowns in afternoon hours. "
        "Pattern follows daily temperature cycle and scanner utilization peaks."
    ),
    governance_alone=(
        "Both scanners failing - investigate common infrastructure. "
        "Major SLA risk with both units affected."
    ),
    hardware_alone=(
        "Individual scanner cooling systems check out. "
        "Shared chilled water supply recently modified."
    ),
    telemetry_alone=(
        "Thermal shutdowns staggered by time of day. "
        "Correlates with building temperature and utilization patterns."
    ),
    emergent_diagnosis=(
        "Reduced chiller capacity insufficient for both scanners during peak loads. "
        "Morning scanner A load saturates cooling, afternoon scanner B load does the same. "
        "The energy savings initiative reduced shared cooling below the combined "
        "thermal demand during peak hours. Restore chiller to original capacity "
        "or stagger scanner schedules to avoid simultaneous peak thermal load. "
        "Root cause is facilities decision, not equipment failure."
    ),
    reasoning_chain=[
        "Governance: 'Both scanners failing simultaneously - unprecedented'",
        "Telemetry: 'Staggered thermal shutdowns follow daily utilization pattern'",
        "Hardware: 'Shared chilled water loop capacity recently reduced'",
        "Synthesis: 'Insufficient shared cooling after capacity reduction'"
    ],
    requires_cross_domain=True,
    difficulty=Difficulty.COMPLEX,
    required_keywords=["cooling", "chiller", "shared", "staggered", "capacity"],
    expected_agent_sequence=["governance_agent", "telemetry_agent", "hardware_agent"],
    domain="healthcare",
    tags=["mri", "cooling", "multi_scanner", "facilities"]
)


# Default test suite
DEFAULT_TEST_SUITE = EmergenceTestSuite(
    name="healthcare_mas_emergence",
    description="Emergence test cases for Healthcare MRI MAS",
    test_cases=[
        # Complex (4 cases)
        CASCADING_THERMAL_FAULT,
        PHANTOM_LOAD_SPIKE,
        GRADIENT_COIL_DEGRADATION,
        HELIUM_BOILOFF_CASCADE,
        SHIMMING_ENVIRONMENTAL,
        MULTI_SCANNER_COOLING,
        # Moderate (4 cases)
        SOFTWARE_UPDATE_REGRESSION,
        RF_AMPLIFIER_INTERMITTENT,
        NETWORK_FALSE_ALARM,
        PROTOCOL_CONFLICT_SLA,
        # Simple (2 cases)
        MISSED_MAINTENANCE_ESCALATION,
        KNOWN_FAULT_CODE_LOOKUP,
    ]
)


def load_test_suite(path: str) -> EmergenceTestSuite:
    """Load test suite from JSON file."""
    with open(path, 'r') as f:
        data = json.load(f)
    return EmergenceTestSuite(**data)


def save_test_suite(suite: EmergenceTestSuite, path: str) -> None:
    """Save test suite to JSON file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(suite.model_dump(), f, indent=2)


def main():
    """Test the emergence test case framework."""
    logger.info("=" * 60)
    logger.info("Testing Emergence Test Cases")
    logger.info("=" * 60)

    # Show default test suite
    logger.info(f"\nTest Suite: {DEFAULT_TEST_SUITE.name}")
    logger.info(f"Description: {DEFAULT_TEST_SUITE.description}")
    logger.info(f"Total test cases: {len(DEFAULT_TEST_SUITE.test_cases)}")

    for tc in DEFAULT_TEST_SUITE.test_cases:
        logger.info(f"\n{'='*40}")
        logger.info(f"Test Case: {tc.name}")
        logger.info(f"Difficulty: {tc.difficulty}")
        logger.info(f"Description: {tc.description}")
        logger.info(f"Required Keywords: {tc.required_keywords}")
        logger.info(f"\nEmergent Diagnosis:")
        logger.info(f"  {tc.emergent_diagnosis}")
        logger.info(f"\nReasoning Chain:")
        for step in tc.reasoning_chain:
            logger.info(f"  - {step}")

    # Save to file
    test_path = "data/scenarios/emergence_tests.json"
    save_test_suite(DEFAULT_TEST_SUITE, test_path)
    logger.info(f"\nSaved test suite to: {test_path}")

    logger.info("\n" + "=" * 60)
    logger.info("Test case framework complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
