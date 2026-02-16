"""
Siemens Data Preprocessing Script

Restructures raw Siemens data into agent-specific processed formats:
- Hardware Agent: Equipment specs, protocol references
- Telemetry Agent: Event logs as structured CSV, failure modes
- Governance Agent: Clinical guidelines, RSNA templates summary

Run: python scripts/preprocess_siemens_data.py
"""

import os
import re
import csv
import json
import math
import shutil
import runpy
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
RAW_SIEMENS = BASE_DIR / "data" / "raw" / "siemens"
PROCESSED = BASE_DIR / "data" / "processed"
HARDWARE_DIR = PROCESSED / "hardware"
TELEMETRY_DIR = PROCESSED / "telemetry"
GOVERNANCE_DIR = PROCESSED / "governance"


def ensure_directories():
    """Create output directories."""
    for d in [HARDWARE_DIR, TELEMETRY_DIR, GOVERNANCE_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    logger.info("Created output directories")


def cleanup_stale_files():
    """Delete known stale files from previous preprocessing runs."""
    stale_files = [
        HARDWARE_DIR / "versicharge_specifications.csv",
        HARDWARE_DIR / "sample_processed_long_format.csv",
        HARDWARE_DIR / "sample_processed_wide_format.csv",
        TELEMETRY_DIR / "mri_events.csv",
        TELEMETRY_DIR / "event_summary.csv",
        TELEMETRY_DIR / "detected_patterns.csv",
        TELEMETRY_DIR / "failure_modes.csv",  # moved to hardware/
    ]
    removed = 0
    for f in stale_files:
        if f.exists():
            f.unlink()
            logger.info(f"  Removed stale file: {f.name}")
            removed += 1
    logger.info(f"Cleanup: removed {removed} stale files")


def preprocess_event_logs():
    """
    Parse MRI event logs into structured CSV for Telemetry Agent.

    Extracts:
    - Timestamp, Level, Source, EventID, Description
    - Categorizes by severity and component
    - Detects patterns (thermal, shutdown, errors)
    """
    eventlog_dir = RAW_SIEMENS / "eventlog_txt"
    if not eventlog_dir.exists():
        logger.warning(f"Event log directory not found: {eventlog_dir}")
        return

    output_csv = TELEMETRY_DIR / "mri_events.csv"
    output_summary = TELEMETRY_DIR / "event_summary.csv"
    output_patterns = TELEMETRY_DIR / "detected_patterns.csv"

    events = []
    severity_counts = defaultdict(int)
    source_counts = defaultdict(int)
    hourly_counts = defaultdict(int)
    pattern_events = []

    # Pattern detection keywords
    thermal_keywords = ['thermal', 'temperature', 'cooling', 'overheat', 'shutdown']
    error_keywords = ['error', 'fail', 'fault', 'exception', 'critical']
    mri_sources = ['syngo', 'MR', 'Siemens']

    for log_file in eventlog_dir.glob("*.txt"):
        logger.info(f"Processing: {log_file.name}")

        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue

                parts = line.strip().split('\t')
                if len(parts) < 6:
                    continue

                try:
                    level = parts[0]
                    date = parts[1]
                    time = parts[2]
                    source = parts[3]
                    event_id = parts[4]
                    description = '\t'.join(parts[5:])

                    # Map level to severity
                    severity_map = {'I': 'info', 'W': 'warning', 'E': 'error'}
                    severity = severity_map.get(level, 'unknown')

                    # Categorize source
                    is_mri_specific = any(s.lower() in source.lower() for s in mri_sources)

                    # Detect patterns
                    desc_lower = description.lower()
                    is_thermal = any(kw in desc_lower for kw in thermal_keywords)
                    is_error = any(kw in desc_lower for kw in error_keywords)

                    event = {
                        'timestamp': f"{date} {time}",
                        'date': date,
                        'time': time,
                        'level': level,
                        'severity': severity,
                        'source': source,
                        'event_id': event_id,
                        'description': description[:500],  # Truncate long descriptions
                        'is_mri_specific': is_mri_specific,
                        'is_thermal': is_thermal,
                        'is_error': is_error
                    }
                    events.append(event)

                    # Track statistics
                    severity_counts[severity] += 1
                    source_counts[source] += 1
                    hourly_counts[f"{date} {time[:2]}:00"] += 1

                    # Track pattern events
                    if is_thermal or (severity == 'error' and is_mri_specific):
                        pattern_events.append(event)

                except Exception as e:
                    if line_num % 10000 == 0:
                        logger.debug(f"Parse error at line {line_num}: {e}")

                if line_num % 50000 == 0:
                    logger.info(f"  Processed {line_num} lines...")

    # Write main events CSV (sample for manageability)
    logger.info(f"Writing {len(events)} events to CSV...")

    # Write full events (or sample if too large)
    if len(events) > 100000:
        # Write sample + all errors/warnings
        sample_events = [e for e in events if e['severity'] != 'info'][:50000]
        sample_events += [e for e in events if e['severity'] == 'info'][:50000]
        events_to_write = sample_events
        logger.info(f"  Sampled to {len(events_to_write)} events (full log too large)")
    else:
        events_to_write = events

    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        if events_to_write:
            writer = csv.DictWriter(f, fieldnames=events_to_write[0].keys())
            writer.writeheader()
            writer.writerows(events_to_write)

    # Write summary statistics
    summary_rows = [
        {'metric': 'total_events', 'value': len(events)},
        {'metric': 'info_count', 'value': severity_counts['info']},
        {'metric': 'warning_count', 'value': severity_counts['warning']},
        {'metric': 'error_count', 'value': severity_counts['error']},
        {'metric': 'unique_sources', 'value': len(source_counts)},
        {'metric': 'mri_specific_events', 'value': sum(1 for e in events if e['is_mri_specific'])},
        {'metric': 'thermal_events', 'value': sum(1 for e in events if e['is_thermal'])},
    ]

    with open(output_summary, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['metric', 'value'])
        writer.writeheader()
        writer.writerows(summary_rows)

    # Write pattern events for analysis
    with open(output_patterns, 'w', newline='', encoding='utf-8') as f:
        if pattern_events:
            writer = csv.DictWriter(f, fieldnames=pattern_events[0].keys())
            writer.writeheader()
            writer.writerows(pattern_events[:10000])  # Limit for analysis

    logger.info(f"Event logs processed:")
    logger.info(f"  - Main events: {output_csv}")
    logger.info(f"  - Summary: {output_summary}")
    logger.info(f"  - Patterns: {output_patterns}")


def preprocess_failure_modes():
    """Generate MRI-specific failure modes CSV for Hardware Agent."""
    dst = HARDWARE_DIR / "failure_modes.csv"

    mri_failure_modes = [
        {"failure_id": "FM-001", "failure_mode": "Thermal Sensor Drift", "component": "Temperature Sensor",
         "symptom": "Intermittent thermal shutdowns every 60-90 minutes; scanner enters safe mode",
         "root_cause": "Sensor calibration drift over time; aging thermistor; environmental contamination",
         "detection_method": "Telemetry pattern analysis; syngo.MR.HostInfra.Telemetry events 50410/50411; thermal threshold alerts",
         "severity": "critical", "mttr_hours": 4,
         "repair_action": "Recalibrate thermal sensor; replace thermistor if out of tolerance; verify cooling system airflow",
         "spare_parts_required": "Temperature sensor module; thermal paste",
         "preventive_maintenance": "Quarterly calibration check; annual sensor replacement evaluation"},
        {"failure_id": "FM-002", "failure_mode": "Gradient Coil Degradation", "component": "Gradient Coil Assembly",
         "symptom": "Image quality complaints; 2-3% increase in scan duration; subtle artifacts in diffusion-weighted sequences",
         "root_cause": "Coil winding insulation breakdown; resistive heating from aging; micro-fractures in cooling channels",
         "detection_method": "Scan timing analysis; image quality metrics trending; manufacturer advisory cross-reference",
         "severity": "high", "mttr_hours": 48,
         "repair_action": "Schedule manufacturer inspection; plan proactive coil replacement; monitor closely until replacement",
         "spare_parts_required": "Gradient coil assembly (long lead time)",
         "preventive_maintenance": "Annual resistance measurement; quarterly performance benchmarking"},
        {"failure_id": "FM-003", "failure_mode": "Helium Level Drop", "component": "Cryostat/Cold Head",
         "symptom": "Helium level alerts; quench risk warning; gradual performance degradation",
         "root_cause": "Cold head compressor wear; minor cryostat leak; ambient temperature exceedance",
         "detection_method": "Helium level sensor trending; compressor cycle monitoring; syngo cryogen alerts",
         "severity": "critical", "mttr_hours": 8,
         "repair_action": "Emergency helium refill; cold head inspection; leak detection with sniffer",
         "spare_parts_required": "Liquid helium; cold head compressor seals",
         "preventive_maintenance": "Monthly helium level check; quarterly compressor inspection"},
        {"failure_id": "FM-004", "failure_mode": "RF Amplifier Intermittent", "component": "RF Power Amplifier",
         "symptom": "Inconsistent signal-to-noise ratio; random scan failures; image brightness variations",
         "root_cause": "Amplifier tube aging; power supply capacitor degradation; thermal cycling fatigue",
         "detection_method": "RF power monitoring; scan failure rate tracking; calibration drift detection",
         "severity": "high", "mttr_hours": 6,
         "repair_action": "Replace RF amplifier tube; recalibrate RF chain; verify power supply stability",
         "spare_parts_required": "RF amplifier tube; power supply capacitors",
         "preventive_maintenance": "Bi-annual tube inspection; annual power supply capacitor check"},
        {"failure_id": "FM-005", "failure_mode": "Software Service Crash", "component": "syngo Application (LCM)",
         "symptom": "Application freeze; scanner unresponsive; automatic service restart; session data loss",
         "root_cause": "Memory leak; unhandled exception; disk space exhaustion; database corruption",
         "detection_method": "syngo_Application restart events; Windows Application event log; LCM service lifecycle events",
         "severity": "medium", "mttr_hours": 1,
         "repair_action": "Restart syngo services; clear temp files; verify disk space; apply software patches",
         "spare_parts_required": "None - software only",
         "preventive_maintenance": "Weekly disk space monitoring; monthly log cleanup; patch management schedule"},
        {"failure_id": "FM-006", "failure_mode": "Patient Table Positioning Error", "component": "Patient Table System",
         "symptom": "Table position inaccurate; scan region misalignment; repeated positioning attempts",
         "root_cause": "Table encoder failure; motor controller drift; mechanical obstruction in rail",
         "detection_method": "Table position sensor errors; motor current anomalies; repeated positioning events in telemetry",
         "severity": "medium", "mttr_hours": 3,
         "repair_action": "Recalibrate table encoders; clean and lubricate rail system; replace motor controller if faulty",
         "spare_parts_required": "Table encoder; motor controller board",
         "preventive_maintenance": "Quarterly table calibration; monthly rail cleaning"},
        {"failure_id": "FM-007", "failure_mode": "Network/DICOM Transfer Failure", "component": "Network Infrastructure",
         "symptom": "Images not appearing in PACS; transfer timeouts; study routing failures",
         "root_cause": "Network switch congestion; DICOM association rejection; DNS resolution failure; firewall rule change",
         "detection_method": "DICOM transfer error logs; network timeout events; PACS connectivity heartbeat failures",
         "severity": "medium", "mttr_hours": 2,
         "repair_action": "Verify network connectivity; check DICOM AE titles; review firewall rules; restart DICOM services",
         "spare_parts_required": "Network cable; switch port module",
         "preventive_maintenance": "Weekly DICOM echo test; monthly network infrastructure review"},
        {"failure_id": "FM-008", "failure_mode": "Coil Connection Fault", "component": "Receive Coil",
         "symptom": "Coil not recognized; signal dropout on specific channels; partial FOV coverage",
         "root_cause": "Coil connector pin damage; cable fatigue from repeated flexion; coil element failure",
         "detection_method": "Coil detection events; channel signal level monitoring; repeated coil reconnection attempts",
         "severity": "medium", "mttr_hours": 1,
         "repair_action": "Clean connector pins; test cable continuity; replace coil if element failed",
         "spare_parts_required": "Receive coil; connector assembly",
         "preventive_maintenance": "Pre-scan coil verification; quarterly connector inspection"},
        {"failure_id": "FM-009", "failure_mode": "Power Supply Fluctuation", "component": "Main Power Distribution",
         "symptom": "Intermittent system resets; gradient amplifier faults; subsystem brown-out events",
         "root_cause": "Facility power quality issues; UPS battery degradation; PDU breaker trips",
         "detection_method": "Power monitoring logs; UPS event alerts; gradient amplifier fault codes",
         "severity": "high", "mttr_hours": 4,
         "repair_action": "Check facility power quality; test UPS battery; verify PDU connections; install power conditioner",
         "spare_parts_required": "UPS batteries; power conditioner",
         "preventive_maintenance": "Monthly UPS battery test; quarterly power quality measurement"},
        {"failure_id": "FM-010", "failure_mode": "Shimming Failure", "component": "Shim System",
         "symptom": "B0 inhomogeneity; fat-water swap artifacts; geometric distortion in large FOV",
         "root_cause": "Shim coil current drift; room temperature variation affecting passive shims; ferromagnetic contamination",
         "detection_method": "Auto-shim failure events; B0 map quality metrics; frequency drift monitoring",
         "severity": "medium", "mttr_hours": 2,
         "repair_action": "Run advanced shimming protocol; check room temperature stability; scan for ferromagnetic sources",
         "spare_parts_required": "Shim iron pieces (passive); shim amplifier (active)",
         "preventive_maintenance": "Monthly shim verification; quarterly room environment check"},
        {"failure_id": "FM-011", "failure_mode": "Image Reconstruction Timeout", "component": "Reconstruction Engine",
         "symptom": "Delayed image availability; queue buildup; timeout errors in syngo",
         "root_cause": "Reconstruction hardware overload; memory exhaustion; corrupted reconstruction pipeline",
         "detection_method": "Reconstruction queue depth; processing time trending; timeout error events",
         "severity": "medium", "mttr_hours": 1,
         "repair_action": "Restart reconstruction engine; clear reconstruction queue; reboot inline processing hardware",
         "spare_parts_required": "None typically - reboot required; GPU board if hardware fault",
         "preventive_maintenance": "Weekly queue monitoring; monthly reconstruction performance benchmark"},
        {"failure_id": "FM-012", "failure_mode": "Bore Fan/Ventilation Failure", "component": "Bore Ventilation System",
         "symptom": "Patient comfort complaints; bore temperature rise; condensation on coils",
         "root_cause": "Fan motor failure; filter blockage; duct obstruction",
         "detection_method": "Bore temperature sensors; fan RPM monitoring; patient comfort feedback correlation",
         "severity": "low", "mttr_hours": 2,
         "repair_action": "Replace fan motor; clean or replace filters; inspect ductwork",
         "spare_parts_required": "Fan motor; ventilation filters",
         "preventive_maintenance": "Quarterly filter replacement; monthly fan operation check"},
        {"failure_id": "FM-013", "failure_mode": "Quench Valve Malfunction", "component": "Quench Protection System",
         "symptom": "Quench valve test failure; false quench alarm; valve stuck open/closed",
         "root_cause": "Valve seal degradation; solenoid failure; sensor calibration drift",
         "detection_method": "Quench valve test events; false alarm frequency; valve position feedback",
         "severity": "critical", "mttr_hours": 6,
         "repair_action": "Replace quench valve assembly; recalibrate valve sensors; verify quench pipe integrity",
         "spare_parts_required": "Quench valve assembly; solenoid",
         "preventive_maintenance": "Annual quench valve test; quarterly sensor verification"},
        {"failure_id": "FM-014", "failure_mode": "ECG Gating Signal Loss", "component": "Physiological Monitoring",
         "symptom": "Cardiac-gated sequences fail; irregular triggering; extended scan times",
         "root_cause": "ECG lead contact degradation; cable damage; interference from gradient switching",
         "detection_method": "ECG signal quality events; gating trigger irregularity; scan duration anomalies on cardiac protocols",
         "severity": "low", "mttr_hours": 0.5,
         "repair_action": "Replace ECG leads; verify lead placement technique; check cable routing for interference",
         "spare_parts_required": "ECG lead set; cable",
         "preventive_maintenance": "Per-patient lead check; quarterly cable inspection"},
        {"failure_id": "FM-015", "failure_mode": "Cryogen Compressor Alarm", "component": "Helium Compressor System",
         "symptom": "Compressor high-pressure alarm; compressor shutdown; helium warming trend",
         "root_cause": "Compressor motor wear; refrigerant leak; dirty heat exchanger; ambient temperature exceedance",
         "detection_method": "Compressor alarm events; pressure/temperature trending; helium boil-off rate increase",
         "severity": "critical", "mttr_hours": 8,
         "repair_action": "Emergency compressor service; clean heat exchangers; check refrigerant charge; verify room cooling",
         "spare_parts_required": "Compressor motor; refrigerant charge; heat exchanger",
         "preventive_maintenance": "Quarterly compressor inspection; monthly heat exchanger cleaning"},
        {"failure_id": "FM-016", "failure_mode": "Scan Protocol Mismatch", "component": "Protocol Engine",
         "symptom": "Wrong sequence executed; parameter override failures; protocol load errors",
         "root_cause": "Protocol database corruption; version mismatch after update; user error in protocol management",
         "detection_method": "Protocol execution logs; parameter comparison alerts; Dot Cockpit version tracking",
         "severity": "medium", "mttr_hours": 1,
         "repair_action": "Resync protocol database; verify Dot Cockpit configuration; retrain users on protocol management",
         "spare_parts_required": "None - configuration only",
         "preventive_maintenance": "Post-update protocol verification; monthly Dot Cockpit audit"},
        {"failure_id": "FM-017", "failure_mode": "Eddy Current Compensation Failure", "component": "Gradient System",
         "symptom": "Geometric distortion; ghosting artifacts; signal oscillation after gradient pulses",
         "root_cause": "Eddy current compensation table outdated; gradient amplifier drift; system temperature change",
         "detection_method": "Image quality metrics; eddy current calibration events; gradient performance monitoring",
         "severity": "medium", "mttr_hours": 3,
         "repair_action": "Recalibrate eddy current compensation; update compensation tables; verify gradient amplifier stability",
         "spare_parts_required": "None - calibration only",
         "preventive_maintenance": "Quarterly eddy current calibration; monthly gradient performance check"},
        {"failure_id": "FM-018", "failure_mode": "SAR Limit Exceeded", "component": "SAR Monitoring System",
         "symptom": "Scan terminated mid-sequence; SAR warning; automatic power reduction",
         "root_cause": "Patient weight entered incorrectly; high-SAR sequence selection; room temperature elevated",
         "detection_method": "SAR monitoring alerts; scan termination events; patient parameter logs",
         "severity": "low", "mttr_hours": 0.5,
         "repair_action": "Verify patient weight; adjust sequence parameters; ensure room temperature compliance",
         "spare_parts_required": "None - procedural",
         "preventive_maintenance": "Pre-scan SAR estimation review; quarterly SAR monitor calibration"},
        {"failure_id": "FM-019", "failure_mode": "Magnet Room Door Interlock", "component": "Safety System",
         "symptom": "Scanner shuts down when door opened during scan; interlock alarm; session interrupted",
         "root_cause": "Door seal sensor failure; interlock relay malfunction; unauthorized door opening",
         "detection_method": "Door interlock events; safety system alerts; session interruption correlation",
         "severity": "medium", "mttr_hours": 1,
         "repair_action": "Test door interlock sensors; replace faulty relay; verify door seal integrity; retrain staff",
         "spare_parts_required": "Door sensor; interlock relay",
         "preventive_maintenance": "Monthly interlock test; quarterly staff safety refresher"},
        {"failure_id": "FM-020", "failure_mode": "System Clock Drift", "component": "Timing System",
         "symptom": "Timestamp inconsistencies in DICOM headers; scheduling conflicts; audit trail discrepancies",
         "root_cause": "NTP synchronization failure; RTC battery depletion; network configuration error",
         "detection_method": "Time deviation alerts; DICOM timestamp analysis; NTP sync failure events",
         "severity": "low", "mttr_hours": 0.5,
         "repair_action": "Resync with NTP server; replace RTC battery; verify network time configuration",
         "spare_parts_required": "RTC battery",
         "preventive_maintenance": "Monthly time sync verification; annual RTC battery check"},
    ]

    fieldnames = list(mri_failure_modes[0].keys())
    with open(dst, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(mri_failure_modes)

    logger.info(f"Generated {len(mri_failure_modes)} MRI failure modes: {dst}")


def preprocess_rsna_templates():
    """
    Extract RSNA RadReport templates into structured CSV for Governance Agent.

    Creates:
    - Template inventory with metadata
    - RadLex terms index
    - Clinical categories summary
    """
    rsna_dir = RAW_SIEMENS / "examination" / "RSNA-RAD-REPORT"
    if not rsna_dir.exists():
        logger.warning(f"RSNA templates not found: {rsna_dir}")
        return

    output_inventory = GOVERNANCE_DIR / "clinical_protocols.csv"
    output_radlex = GOVERNANCE_DIR / "radlex_terms.csv"
    output_categories = GOVERNANCE_DIR / "protocol_categories.csv"

    templates = []
    radlex_terms = []
    categories = defaultdict(int)

    # Category detection
    modality_keywords = {
        'CT': ['ct ', 'computed tomography', 'scan'],
        'MRI': ['mri', 'mr ', 'magnetic resonance'],
        'Xray': ['xray', 'x-ray', 'radiograph'],
        'Ultrasound': ['ultrasound', 'us ', 'echo'],
        'Nuclear': ['nuclear', 'pet', 'spect', 'scintigraphy'],
        'Fluoroscopy': ['fluoro', 'fluoroscopy'],
    }

    body_region_keywords = {
        'Head/Brain': ['head', 'brain', 'cerebr', 'skull', 'cranial'],
        'Chest': ['chest', 'thorax', 'lung', 'pulmonary', 'cardiac'],
        'Abdomen': ['abdomen', 'abdominal', 'liver', 'kidney', 'pancrea'],
        'Pelvis': ['pelvis', 'pelvic', 'bladder', 'prostate', 'uterus'],
        'Spine': ['spine', 'spinal', 'lumbar', 'cervical', 'thoracic'],
        'Extremity': ['extremity', 'arm', 'leg', 'hand', 'foot', 'ankle'],
        'Vascular': ['angio', 'vascular', 'vessel', 'artery', 'vein'],
    }

    # RadLex extraction pattern
    radlex_pattern = re.compile(r'<code\s+meaning="([^"]+)"\s+value="(RID\d+)"\s+scheme="RadLex"', re.IGNORECASE)

    for template_file in rsna_dir.glob("*.txt"):
        try:
            with open(template_file, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            filename = template_file.stem

            # Extract metadata
            title_match = re.search(r'name="dcterms.title"\s+content="([^"]+)"', content)
            title = title_match.group(1) if title_match else filename

            desc_match = re.search(r'name="dcterms.description"\s+content="([^"]+)"', content)
            description = desc_match.group(1) if desc_match else ""

            lang_match = re.search(r'name="dcterms.language"\s+content="([^"]+)"', content)
            language = lang_match.group(1) if lang_match else "en"

            # Detect modality
            title_lower = title.lower()
            modality = "Other"
            for mod, keywords in modality_keywords.items():
                if any(kw in title_lower for kw in keywords):
                    modality = mod
                    break

            # Detect body region
            body_region = "General"
            for region, keywords in body_region_keywords.items():
                if any(kw in title_lower for kw in keywords):
                    body_region = region
                    break

            # Extract RadLex terms
            for match in radlex_pattern.finditer(content):
                meaning, code = match.groups()
                radlex_terms.append({
                    'template': filename,
                    'code': code,
                    'meaning': meaning
                })

            template = {
                'filename': filename,
                'title': title,
                'description': description[:200] if description else "",
                'language': language,
                'modality': modality,
                'body_region': body_region,
                'file_size_bytes': template_file.stat().st_size
            }
            templates.append(template)

            # Track categories
            categories[f"{modality}_{body_region}"] += 1

        except Exception as e:
            logger.warning(f"Error processing {template_file.name}: {e}")

    # Write templates inventory
    with open(output_inventory, 'w', newline='', encoding='utf-8') as f:
        if templates:
            writer = csv.DictWriter(f, fieldnames=templates[0].keys())
            writer.writeheader()
            writer.writerows(templates)

    # Write RadLex terms
    with open(output_radlex, 'w', newline='', encoding='utf-8') as f:
        if radlex_terms:
            writer = csv.DictWriter(f, fieldnames=radlex_terms[0].keys())
            writer.writeheader()
            writer.writerows(radlex_terms)

    # Write categories summary
    category_rows = [{'category': k, 'count': v} for k, v in sorted(categories.items(), key=lambda x: -x[1])]
    with open(output_categories, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['category', 'count'])
        writer.writeheader()
        writer.writerows(category_rows)

    logger.info(f"RSNA templates processed:")
    logger.info(f"  - Protocols inventory: {output_inventory} ({len(templates)} templates)")
    logger.info(f"  - RadLex terms: {output_radlex} ({len(radlex_terms)} terms)")
    logger.info(f"  - Categories: {output_categories}")


def preprocess_hardware_specs():
    """
    Create hardware specifications index for Hardware Agent.

    Copies relevant CSVs and creates PDF index.
    """
    output_pdf_index = HARDWARE_DIR / "documentation_index.csv"

    # Create PDF documentation index (exclude versicharge and duplicate PDFs)
    pdf_docs = []
    pdf_categories = {
        'DCS_MR': 'System Specifications',
        'MAGNETOM': 'Hardware Specifications',
        'Protocol': 'Protocol Management',
        'MRI-SOP': 'Operating Procedures',
        'Safety': 'Safety Guidelines',
        'Interpretation': 'Clinical Interpretation',
        'ACR': 'Clinical Guidelines'
    }

    for pdf_file in RAW_SIEMENS.glob("*.pdf"):
        # Skip versicharge PDFs (not MRI-related)
        if 'versicharge' in pdf_file.name.lower():
            continue
        # Skip duplicate PDFs (Windows copy artifacts like "file (1).pdf")
        if ' (1)' in pdf_file.name:
            continue

        category = "General"
        for keyword, cat in pdf_categories.items():
            if keyword.lower() in pdf_file.name.lower():
                category = cat
                break

        pdf_docs.append({
            'filename': pdf_file.name,
            'category': category,
            'size_mb': round(pdf_file.stat().st_size / (1024 * 1024), 2),
            'path': str(pdf_file.relative_to(BASE_DIR))
        })

    with open(output_pdf_index, 'w', newline='', encoding='utf-8') as f:
        if pdf_docs:
            writer = csv.DictWriter(f, fieldnames=pdf_docs[0].keys())
            writer.writeheader()
            writer.writerows(pdf_docs)

    logger.info(f"Hardware specs processed:")
    logger.info(f"  - PDF index: {output_pdf_index} ({len(pdf_docs)} documents)")


def preprocess_dcs_pdfs():
    """
    Extract DICOM SOP Class tables from DCS PDFs for The Specialist (Agent 1).

    Uses pdfplumber to parse structured tables containing SOP Class UIDs,
    transfer syntaxes, and roles from DICOM Conformance Statements.
    """
    import sys
    sys.path.insert(0, str(BASE_DIR))

    from src.preprocessing.pdf_extractor import MRIPDFExtractor

    extractor = MRIPDFExtractor()

    # DCS PDFs to process
    dcs_pdfs = [
        RAW_SIEMENS / "DCS_MR_XA50.pdf",
        RAW_SIEMENS / "DCS_MR_XA51A-V03.pdf",
        RAW_SIEMENS / "DCS_MR_XA60.pdf",
    ]
    existing_pdfs = [p for p in dcs_pdfs if p.exists()]

    if not existing_pdfs:
        logger.warning("No DCS PDFs found")
        return

    output = HARDWARE_DIR / "dicom_sop_classes.csv"
    count = extractor.export_sop_classes_to_csv(existing_pdfs, output)
    logger.info(f"DCS processing: {count} SOP Class entries from {len(existing_pdfs)} PDFs")


def preprocess_questionnaires():
    """
    Parse MRRT questionnaire data for The Anthropologist (Agent 2).

    Extracts institution profiles from the pre-parsed CSV data.
    """
    # Check source data exists before attempting parse
    source_csv = RAW_SIEMENS / "sample_processed_long_format.csv"
    if not source_csv.exists():
        logger.error(
            f"MISSING: {source_csv}\n"
            "  This file is required for institution profile generation.\n"
            "  It should contain pre-parsed MRRT questionnaire responses in long format.\n"
            "  Skipping questionnaire preprocessing."
        )
        return

    import sys
    sys.path.insert(0, str(BASE_DIR))

    from src.preprocessing.questionnaire_parser import MRRTQuestionnaireParser

    parser = MRRTQuestionnaireParser(str(RAW_SIEMENS))
    output = GOVERNANCE_DIR / "institution_profiles.csv"
    count = parser.export_profiles(str(output))
    logger.info(f"Questionnaire processing: {count} institution profiles")


def preprocess_safety_docs():
    """
    Extract safety procedures from MRI-SOP PDFs for The Auditor (Agent 3).

    Produces:
    - safety_procedures.csv: Extracted SOP procedures with compliance categories
    - safety_zones.csv: MRI safety zone definitions (Zone I-IV)
    """
    import sys
    sys.path.insert(0, str(BASE_DIR))

    from src.preprocessing.pdf_extractor import MRIPDFExtractor

    extractor = MRIPDFExtractor(chunk_size=800, chunk_overlap=150)

    safety_pdfs = [
        RAW_SIEMENS / "MRI-SOP.pdf",
        RAW_SIEMENS / "SOP-MRI-Safety-Training.jpm-jrs.pdf",
        RAW_SIEMENS / "ACRAppropriatenessCriteria.pdf",
    ]

    # Extract and chunk safety PDFs
    all_chunks = []
    for pdf_path in safety_pdfs:
        if pdf_path.exists():
            chunks = extractor.extract_with_chunking(
                pdf_path,
                extra_metadata={'agent': 'safety_auditor'}
            )
            all_chunks.extend(chunks)
        else:
            logger.warning(f"Safety PDF not found: {pdf_path}")

    # Write safety procedures CSV
    procedures_path = TELEMETRY_DIR / "safety_procedures.csv"
    with open(procedures_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'chunk_id', 'source_file', 'page', 'category', 'content'
        ])
        writer.writeheader()
        for i, chunk in enumerate(all_chunks):
            writer.writerow({
                'chunk_id': f"SP-{i:04d}",
                'source_file': chunk.metadata.get('file_name', ''),
                'page': chunk.metadata.get('page', ''),
                'category': chunk.metadata.get('category', 'safety_sop'),
                'content': chunk.page_content[:2000],
            })

    logger.info(f"Safety docs: {len(all_chunks)} chunks from {len(safety_pdfs)} PDFs -> {procedures_path}")

    # Generate safety zones reference (static for MRI safety zones)
    zones_path = TELEMETRY_DIR / "safety_zones.csv"
    zones = [
        {"zone": "Zone I", "name": "General Public Area",
         "description": "Area freely accessible to the general public. No MRI-specific restrictions.",
         "access": "Unrestricted", "screening_required": "No"},
        {"zone": "Zone II", "name": "Interface/Reception Area",
         "description": "Transition between public and MRI-controlled areas. Patient screening begins here.",
         "access": "Supervised", "screening_required": "MRI screening form"},
        {"zone": "Zone III", "name": "MRI Environment/Control Room",
         "description": "Physical access restricted by key lock or code. Only screened individuals allowed.",
         "access": "Restricted - screened personnel only", "screening_required": "Yes - ferromagnetic screening"},
        {"zone": "Zone IV", "name": "Magnet Room / Scanner Room",
         "description": "Contains the MRI magnet. Highest restriction level. Strong magnetic field always present.",
         "access": "Strictly restricted - Level 2 MR personnel only", "screening_required": "Yes - full screening + supervision"},
    ]
    with open(zones_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=zones[0].keys())
        writer.writeheader()
        writer.writerows(zones)

    logger.info(f"Safety zones: {zones_path}")


def preprocess_eventlog_summaries():
    """
    Generate per-customer error profiles and workload patterns from event log data.

    Uses the pre-computed *_summary.csv files to avoid scanning full parquet.
    """
    eventlog_dir = RAW_SIEMENS / "eventlog_txt"
    if not eventlog_dir.exists():
        logger.warning(f"Event log directory not found: {eventlog_dir}")
        return

    import pandas as pd

    # Per-customer error profiles for The Specialist (Agent 1)
    error_profiles = []
    for customer_dir in sorted(eventlog_dir.iterdir()):
        if not customer_dir.is_dir() or not customer_dir.name.startswith('mr'):
            continue

        cid = customer_dir.name
        summary_path = customer_dir / f"{cid}_summary.csv"
        if not summary_path.exists():
            continue

        try:
            df = pd.read_csv(summary_path)
            errors = df[df['level'] == 'E']
            warnings = df[df['level'] == 'W']

            total_error_count = int(errors['occurrence_count'].sum()) if not errors.empty else 0
            total_warning_count = int(warnings['occurrence_count'].sum()) if not warnings.empty else 0

            top_error_sources = (
                errors.groupby('source')['occurrence_count'].sum()
                .nlargest(5)
                .to_dict() if not errors.empty else {}
            )

            error_profiles.append({
                'customer_id': cid,
                'total_error_events': total_error_count,
                'total_warning_events': total_warning_count,
                'unique_error_patterns': len(errors),
                'unique_warning_patterns': len(warnings),
                'top_error_source_1': list(top_error_sources.keys())[0] if top_error_sources else '',
                'top_error_source_1_count': list(top_error_sources.values())[0] if top_error_sources else 0,
                'top_error_source_2': list(top_error_sources.keys())[1] if len(top_error_sources) > 1 else '',
                'top_error_source_2_count': list(top_error_sources.values())[1] if len(top_error_sources) > 1 else 0,
                'top_error_source_3': list(top_error_sources.keys())[2] if len(top_error_sources) > 2 else '',
                'top_error_source_3_count': list(top_error_sources.values())[2] if len(top_error_sources) > 2 else 0,
            })
        except Exception as e:
            logger.warning(f"Failed to process summary for {cid}: {e}")

    if error_profiles:
        profiles_path = HARDWARE_DIR / "per_customer_error_profiles.csv"
        pd.DataFrame(error_profiles).to_csv(profiles_path, index=False)
        logger.info(f"Error profiles: {len(error_profiles)} customers -> {profiles_path}")

    # Safety event flags for The Auditor (Agent 3)
    safety_events = []
    safety_keywords = ['quench', 'thermal', 'emergency', 'safety', 'interlock',
                        'shutdown', 'helium', 'cryo', 'sar limit']

    for customer_dir in sorted(eventlog_dir.iterdir()):
        if not customer_dir.is_dir() or not customer_dir.name.startswith('mr'):
            continue

        cid = customer_dir.name
        summary_path = customer_dir / f"{cid}_summary.csv"
        if not summary_path.exists():
            continue

        try:
            df = pd.read_csv(summary_path)
            for _, row in df.iterrows():
                desc = str(row.get('masked_description', '')).lower()
                matched_keywords = [kw for kw in safety_keywords if kw in desc]
                if matched_keywords:
                    safety_events.append({
                        'customer_id': cid,
                        'level': row.get('level', ''),
                        'source': row.get('source', ''),
                        'event_id': row.get('event_id', ''),
                        'description': str(row.get('masked_description', ''))[:500],
                        'occurrence_count': row.get('occurrence_count', 0),
                        'safety_keyword': matched_keywords[0],
                    })
        except Exception as e:
            logger.warning(f"Failed to scan safety events for {cid}: {e}")

    if safety_events:
        safety_path = TELEMETRY_DIR / "safety_event_flags.csv"
        pd.DataFrame(safety_events).to_csv(safety_path, index=False)
        logger.info(f"Safety events: {len(safety_events)} flagged events -> {safety_path}")


def preprocess_workload_patterns():
    """
    Generate workload patterns CSV for Governance Agent (GAP 1).

    Reads per-customer summary CSVs and all_customers_overview.csv to compute
    workload metrics per customer including event diversity (Shannon entropy).
    """
    import pandas as pd

    eventlog_dir = RAW_SIEMENS / "eventlog_txt"
    overview_path = eventlog_dir / "all_customers_overview.csv"

    if not eventlog_dir.exists():
        logger.warning(f"Event log directory not found: {eventlog_dir}")
        return

    # Load overview for aggregate stats
    overview_stats = {}
    if overview_path.exists():
        ov_df = pd.read_csv(overview_path)
        for _, row in ov_df.iterrows():
            overview_stats[row['customer']] = row.to_dict()

    patterns = []
    for customer_dir in sorted(eventlog_dir.iterdir()):
        if not customer_dir.is_dir() or not customer_dir.name.startswith('mr'):
            continue

        cid = customer_dir.name
        summary_path = customer_dir / f"{cid}_summary.csv"
        if not summary_path.exists():
            continue

        try:
            df = pd.read_csv(summary_path)
            ov = overview_stats.get(cid, {})

            total_events = int(ov.get('total_events', df['occurrence_count'].sum()))
            mri_events = int(ov.get('mri_events', 0))
            mri_pct = float(ov.get('mri_pct', 0.0))
            errors = int(ov.get('errors', 0))
            warnings = int(ov.get('warnings', 0))

            error_rate = round(errors / total_events, 4) if total_events > 0 else 0.0
            warning_rate = round(warnings / total_events, 4) if total_events > 0 else 0.0

            # Source distribution for top sources and diversity
            source_counts = df.groupby('source')['occurrence_count'].sum().sort_values(ascending=False)
            unique_sources = len(source_counts)
            top_sources = source_counts.head(1)
            top_source_1 = top_sources.index[0] if len(top_sources) > 0 else ''
            top_source_1_pct = round(float(top_sources.iloc[0]) / total_events, 4) if (len(top_sources) > 0 and total_events > 0) else 0.0

            # Shannon entropy for event diversity
            total_occ = source_counts.sum()
            if total_occ > 0 and unique_sources > 1:
                probs = source_counts / total_occ
                diversity_index = round(-sum(p * math.log2(p) for p in probs if p > 0), 4)
            else:
                diversity_index = 0.0

            unique_patterns = len(df)

            patterns.append({
                'customer_id': cid,
                'total_events': total_events,
                'total_unique_patterns': unique_patterns,
                'mri_events': mri_events,
                'mri_pct': mri_pct,
                'error_rate': error_rate,
                'warning_rate': warning_rate,
                'top_source_1': top_source_1,
                'top_source_1_pct': top_source_1_pct,
                'unique_sources': unique_sources,
                'event_diversity_index': diversity_index,
            })
        except Exception as e:
            logger.warning(f"Failed to compute workload patterns for {cid}: {e}")

    if patterns:
        output_path = GOVERNANCE_DIR / "workload_patterns.csv"
        pd.DataFrame(patterns).to_csv(output_path, index=False)
        logger.info(f"Workload patterns: {len(patterns)} customers -> {output_path}")
    else:
        logger.warning("No workload patterns generated")


def preprocess_personnel_requirements():
    """
    Generate personnel requirements CSV for Telemetry Agent (GAP 2).

    Static reference data based on ACR MRI safety standards.
    """
    roles = [
        {
            'role': 'Level 1 MR Personnel',
            'level': 1,
            'zone_access': 'Zones I-III',
            'supervision_required': 'Yes - by Level 2 in Zone III',
            'training_requirements': 'MR safety orientation; site-specific safety training',
            'certification': 'Facility-specific MR safety training completion',
        },
        {
            'role': 'Level 2 MR Personnel',
            'level': 2,
            'zone_access': 'Zones I-IV',
            'supervision_required': 'No',
            'training_requirements': 'Extensive MR safety education; hands-on MR experience; ongoing CE',
            'certification': 'ARRT(MR) or equivalent; ACR-recommended MR safety training',
        },
        {
            'role': 'MR Medical Director',
            'level': 2,
            'zone_access': 'Zones I-IV',
            'supervision_required': 'No',
            'training_requirements': 'Board-certified radiologist; MR physics training; safety program oversight',
            'certification': 'Board certification in Radiology; MR safety officer qualification',
        },
        {
            'role': 'MR Safety Officer',
            'level': 2,
            'zone_access': 'Zones I-IV',
            'supervision_required': 'No',
            'training_requirements': 'MR safety expertise; emergency procedure training; policy development',
            'certification': 'MRSO certification (ABMRS) or equivalent; annual safety training renewal',
        },
    ]

    output_path = TELEMETRY_DIR / "personnel_requirements.csv"
    fieldnames = list(roles[0].keys())
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(roles)

    logger.info(f"Personnel requirements: {len(roles)} roles -> {output_path}")


def preprocess_customer_mapping():
    """
    Generate customer mapping CSV by calling build_customer_mapping.build_mapping() (GAP 3).

    Uses runpy to avoid package import issues with scripts/ directory.
    """
    mapping_script = BASE_DIR / "scripts" / "build_customer_mapping.py"
    if not mapping_script.exists():
        logger.warning(f"build_customer_mapping.py not found: {mapping_script}")
        return

    try:
        module = runpy.run_path(str(mapping_script))
        build_fn = module.get('build_mapping')
        if build_fn:
            build_fn()
            logger.info("Customer mapping generated via build_customer_mapping")
        else:
            logger.error("build_mapping() function not found in build_customer_mapping.py")
    except Exception as e:
        logger.error(f"Failed to run customer mapping builder: {e}")


def validate_agent_config():
    """
    Validate that config/data_config.json references existing files (GAP 10).

    Replaces create_agent_config() — does NOT overwrite the clean config.
    Instead, reads the existing config and checks that every referenced file exists.
    """
    config_path = BASE_DIR / "config" / "data_config.json"
    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}")
        return

    with open(config_path, 'r') as f:
        config = json.load(f)

    logger.info(f"Validating data config v{config.get('data_version', '?')}...")
    all_ok = True

    for agent_name, agent_cfg in config.get('agents', {}).items():
        data_dir = BASE_DIR / agent_cfg.get('data_dir', '')
        files = agent_cfg.get('files', [])
        for fname in files:
            fpath = data_dir / fname
            if not fpath.exists():
                logger.warning(f"  MISSING: {agent_name} -> {fname} (expected at {fpath})")
                all_ok = False
            else:
                logger.info(f"  OK: {agent_name} -> {fname}")

    # Check shared files
    for key, path_str in config.get('shared', {}).items():
        fpath = BASE_DIR / path_str
        if not fpath.exists():
            logger.warning(f"  MISSING shared: {key} -> {path_str}")
            all_ok = False
        else:
            logger.info(f"  OK shared: {key}")

    if all_ok:
        logger.info("Config validation: ALL files present")
    else:
        logger.warning("Config validation: some files missing (see warnings above)")


# Legacy function — kept for reference but no longer called from main()
def create_agent_config():
    """Create configuration file for agent data paths. DEPRECATED — use validate_agent_config()."""
    logger.warning("create_agent_config() is deprecated. Use validate_agent_config() instead.")


def main():
    """Run all preprocessing steps."""
    parser = argparse.ArgumentParser(description="Siemens MRI Data Preprocessing - 3-Agent MAS")
    parser.add_argument('--no-cleanup', action='store_true', help='Skip cleanup of stale files')
    parser.add_argument('--skip-rsna', action='store_true', help='Skip RSNA template processing')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("SIEMENS DATA PREPROCESSING - 3-Agent MAS")
    logger.info("=" * 60)

    logger.info("\n[1/13] Creating output directories...")
    ensure_directories()

    if not args.no_cleanup:
        logger.info("\n[2/13] Cleaning up stale files...")
        cleanup_stale_files()
    else:
        logger.info("\n[2/13] Skipping cleanup (--no-cleanup)")

    if not args.skip_rsna:
        logger.info("\n[3/13] Processing RSNA Templates for Governance...")
        preprocess_rsna_templates()
    else:
        logger.info("\n[3/13] Skipping RSNA templates (--skip-rsna)")

    logger.info("\n[4/13] Processing Hardware Specs & PDF Index...")
    preprocess_hardware_specs()

    logger.info("\n[5/13] Extracting DICOM SOP Classes from DCS PDFs...")
    preprocess_dcs_pdfs()

    logger.info("\n[6/13] Parsing MRRT Questionnaires for Institution Profiles...")
    preprocess_questionnaires()

    logger.info("\n[7/13] Extracting Safety Procedures from SOP PDFs...")
    preprocess_safety_docs()

    logger.info("\n[8/13] Generating Failure Modes (-> hardware/)...")
    preprocess_failure_modes()

    logger.info("\n[9/13] Generating Event Log Summaries & Safety Flags...")
    preprocess_eventlog_summaries()

    logger.info("\n[10/13] Generating Workload Patterns...")
    preprocess_workload_patterns()

    logger.info("\n[11/13] Generating Personnel Requirements...")
    preprocess_personnel_requirements()

    logger.info("\n[12/13] Building Customer Mapping...")
    preprocess_customer_mapping()

    logger.info("\n[13/13] Validating Agent Configuration...")
    validate_agent_config()

    logger.info("\n" + "=" * 60)
    logger.info("PREPROCESSING COMPLETE")
    logger.info("=" * 60)

    logger.info("\nData Structure:")
    logger.info("  data/processed/")
    logger.info("    hardware/    - DCS DICOM tables, error profiles, failure modes, PDF index")
    logger.info("    telemetry/   - Safety SOPs, zones, personnel reqs, event flags")
    logger.info("    governance/  - Institution profiles, workload patterns, clinical protocols")
    logger.info("    customer_mapping.csv  - Customer-to-institution mapping")


if __name__ == "__main__":
    main()
