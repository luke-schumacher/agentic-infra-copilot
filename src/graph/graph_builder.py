"""
Knowledge Graph Builder

Purpose:
- Constructs the infrastructure fault diagnosis Knowledge Graph
- Defines graph schema (nodes: Device, Error, Procedure, Event, etc.)
- Ingests processed data from all three domains (Telekom, Siemens, Illigo)
- Creates relationships between entities (CAUSES, RESOLVES, OCCURS_IN, etc.)

Input: Processed data from data loaders or processed files
Output: Populated Neo4j Knowledge Graph

Usage:
    from src.graph.neo4j_connector import Neo4jConnector
    from src.graph.graph_builder import GraphBuilder

    with Neo4jConnector() as connector:
        builder = GraphBuilder(connector)
        builder.create_schema()
        builder.ingest_telekom_data(telekom_docs)
        builder.ingest_siemens_data(siemens_docs)
        builder.ingest_illigo_data(illigo_events)
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import re

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.graph.neo4j_connector import Neo4jConnector

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builder for the infrastructure fault diagnosis Knowledge Graph."""

    # Define graph schema - MRI Healthcare Domain
    NODE_LABELS = {
        "Scanner": ["scanner_id", "model", "manufacturer", "location", "install_date"],
        "Component": ["component_id", "name", "type", "scanner_id", "expected_life_years"],
        "Fault": ["fault_id", "failure_mode", "severity", "component", "mttr_hours"],
        "Event": ["event_id", "timestamp", "level", "source", "description"],
        "Protocol": ["protocol_id", "title", "modality", "body_region"],
        "SLA": ["sla_id", "name", "metric", "threshold", "domain"],
        "RadLexTerm": ["code", "meaning"],
        # Legacy types kept for backward compatibility
        "Device": ["device_id", "name", "type", "manufacturer", "location"],
        "Error": ["error_code", "description", "severity", "domain"],
        "Procedure": ["procedure_id", "name", "steps", "domain"],
        "Hardware": ["hardware_id", "model", "manufacturer", "institution"],
        "Station": ["station_id", "name", "location", "connector_count"],
    }

    RELATIONSHIP_TYPES = {
        "CAUSES": "Fault or Event causes another Fault or Event",
        "RESOLVES": "Procedure or repair action resolves a Fault",
        "DETECTED_BY": "Fault detected by telemetry event pattern",
        "PART_OF": "Component is part of Scanner",
        "VIOLATES": "Fault or Event violates an SLA",
        "TRIGGERS": "Event triggers a Fault mode",
        "AFFECTS": "Fault affects a Component",
        "USES_TERM": "Protocol uses a RadLex term",
        "OCCURS_IN": "Event occurs in a Scanner or Component",
        "FOLLOWS": "Event follows another Event in sequence",
        "REQUIRES": "Procedure requires a specific Component or part",
        "HAS_HARDWARE": "Scanner has Hardware component",
        "RELATED_TO": "Generic relationship for related entities",
    }

    def __init__(self, connector: Neo4jConnector):
        """
        Initialize the graph builder.

        Args:
            connector: Neo4j database connector
        """
        self.connector = connector

    def create_schema(self):
        """
        Create graph schema (constraints and indexes).
        """
        logger.info("Creating graph schema")

        # Create uniqueness constraints for each node type
        constraints = [
            ("Scanner", "scanner_id"),
            ("Component", "component_id"),
            ("Fault", "fault_id"),
            ("Event", "event_id"),
            ("Protocol", "protocol_id"),
            ("SLA", "sla_id"),
            ("RadLexTerm", "code"),
            # Legacy types
            ("Device", "device_id"),
            ("Error", "error_code"),
            ("Procedure", "procedure_id"),
            ("Hardware", "hardware_id"),
            ("Station", "station_id"),
        ]

        for label, property_name in constraints:
            try:
                # Neo4j 5.x syntax for constraints
                constraint_name = f"constraint_{label.lower()}_{property_name}"
                query = f"""
                CREATE CONSTRAINT {constraint_name} IF NOT EXISTS
                FOR (n:{label})
                REQUIRE n.{property_name} IS UNIQUE
                """
                self.connector.execute_query(query)
                logger.debug(f"Created constraint for {label}.{property_name}")
            except Exception as e:
                # Constraint might already exist
                logger.debug(f"Constraint for {label}.{property_name}: {e}")

        # Create indexes for frequently queried properties
        indexes = [
            ("Scanner", "model"),
            ("Scanner", "location"),
            ("Component", "type"),
            ("Component", "scanner_id"),
            ("Fault", "severity"),
            ("Fault", "failure_mode"),
            ("Event", "timestamp"),
            ("Event", "level"),
            ("Event", "source"),
            ("Protocol", "modality"),
            ("Protocol", "body_region"),
            ("RadLexTerm", "meaning"),
            # Legacy indexes
            ("Device", "type"),
            ("Error", "severity"),
            ("Hardware", "manufacturer"),
        ]

        for label, property_name in indexes:
            try:
                index_name = f"index_{label.lower()}_{property_name}"
                query = f"""
                CREATE INDEX {index_name} IF NOT EXISTS
                FOR (n:{label})
                ON (n.{property_name})
                """
                self.connector.execute_query(query)
                logger.debug(f"Created index for {label}.{property_name}")
            except Exception as e:
                logger.debug(f"Index for {label}.{property_name}: {e}")

        logger.info("Graph schema creation complete")

    def ingest_telekom_data(self, data: List[Dict[str, Any]]):
        """
        Ingest processed Telekom documentation data into the graph.

        Creates Device, Error, Procedure, and SLA nodes with relationships.

        Args:
            data: List of processed Telekom documents (from TelekomLoader)
        """
        logger.info(f"Ingesting {len(data)} Telekom documents")

        procedures_created = 0
        errors_created = 0
        slas_created = 0

        for doc in data:
            content = doc.get("content", doc.get("page_content", ""))
            metadata = doc.get("metadata", {})
            file_name = metadata.get("file_name", "unknown")
            doc_type = metadata.get("doc_type", "general")

            # Extract entities from content
            # Look for error codes (CX001, CX002, etc.)
            error_codes = re.findall(r'CX\d{3}', content)
            for error_code in set(error_codes):
                self.connector.create_node(
                    "Error",
                    {
                        "error_code": error_code,
                        "domain": "telekom",
                        "source_file": file_name,
                        "severity": self._infer_severity(content)
                    },
                    unique_key="error_code"
                )
                errors_created += 1

            # Look for SLA references
            sla_matches = re.findall(r'SLA[-_]?\w+[-_]?\d+', content, re.IGNORECASE)
            for sla_id in set(sla_matches):
                sla_id_clean = sla_id.upper().replace("_", "-")
                self.connector.create_node(
                    "SLA",
                    {
                        "sla_id": sla_id_clean,
                        "domain": "telekom",
                        "source_file": file_name,
                    },
                    unique_key="sla_id"
                )
                slas_created += 1

            # Create procedure nodes for resolution documents
            if "procedure" in doc_type.lower() or "resolution" in content.lower():
                proc_id = f"PROC-TEL-{hash(content) % 10000:04d}"
                self.connector.create_node(
                    "Procedure",
                    {
                        "procedure_id": proc_id,
                        "domain": "telekom",
                        "source_file": file_name,
                        "description": content[:500]
                    },
                    unique_key="procedure_id"
                )
                procedures_created += 1

                # Link procedure to errors it resolves
                for error_code in set(error_codes):
                    self.connector.create_relationship(
                        "Procedure", "procedure_id", proc_id,
                        "Error", "error_code", error_code,
                        "RESOLVES"
                    )

        logger.info(
            f"Telekom ingestion complete: {procedures_created} procedures, "
            f"{errors_created} errors, {slas_created} SLAs"
        )

    def ingest_siemens_data(self, data: List[Dict[str, Any]]):
        """
        Ingest processed Siemens hardware scan data into the graph.

        Creates Hardware nodes and links to institutions/errors.

        Args:
            data: List of processed Siemens scan records (from SiemensLoader)
        """
        logger.info(f"Ingesting {len(data)} Siemens scan records")

        hardware_created = 0
        institutions_seen = set()

        for doc in data:
            content = doc.get("content", doc.get("page_content", ""))
            metadata = doc.get("metadata", {})
            institution = metadata.get("institution", "unknown")

            # Track institutions
            institutions_seen.add(institution)

            # Extract equipment types from content
            equipment_types = []
            if "linac" in content.lower():
                equipment_types.append("LINAC")
            if "ct" in content.lower() or "computed tomography" in content.lower():
                equipment_types.append("CT")
            if "mr" in content.lower() or "mri" in content.lower():
                equipment_types.append("MRI")
            if "coil" in content.lower():
                equipment_types.append("RF_COIL")

            for eq_type in equipment_types:
                hardware_id = f"HW-{institution[:3].upper()}-{eq_type}"
                self.connector.create_node(
                    "Hardware",
                    {
                        "hardware_id": hardware_id,
                        "type": eq_type,
                        "manufacturer": "Siemens",
                        "institution": institution,
                        "domain": "siemens"
                    },
                    unique_key="hardware_id"
                )
                hardware_created += 1

            # Check for pain points / errors in content
            if "pain point" in content.lower() or "issue" in content.lower():
                error_id = f"ERR-SIEM-{hash(content) % 10000:04d}"
                self.connector.create_node(
                    "Error",
                    {
                        "error_code": error_id,
                        "domain": "siemens",
                        "description": content[:300],
                        "severity": "medium"
                    },
                    unique_key="error_code"
                )

                # Link hardware to detected errors
                for eq_type in equipment_types:
                    hardware_id = f"HW-{institution[:3].upper()}-{eq_type}"
                    self.connector.create_relationship(
                        "Hardware", "hardware_id", hardware_id,
                        "Error", "error_code", error_id,
                        "DETECTED_BY"
                    )

        logger.info(
            f"Siemens ingestion complete: {hardware_created} hardware nodes, "
            f"{len(institutions_seen)} institutions"
        )

    def ingest_illigo_data(self, data: List[Dict[str, Any]]):
        """
        Ingest processed Illigo event logs into the graph.

        Creates Station, Event, and Error nodes with relationships.

        Args:
            data: List of processed Illigo events (from IlligoLoader)
        """
        logger.info(f"Ingesting {len(data)} Illigo events")

        stations_created = 0
        events_created = 0
        errors_created = 0

        for doc in data:
            content = doc.get("content", doc.get("page_content", ""))
            metadata = doc.get("metadata", {})
            data_type = metadata.get("data_type", "general")
            station_id = metadata.get("station_id", metadata.get("site", "unknown"))

            # Create station node
            if station_id and station_id != "unknown":
                self.connector.create_node(
                    "Station",
                    {
                        "station_id": station_id.upper(),
                        "domain": "illigo",
                        "location": metadata.get("location", "Abidjan")
                    },
                    unique_key="station_id"
                )
                stations_created += 1

            # Create event nodes for fault events
            if data_type == "fault_event" or "fault" in content.lower():
                event_id = metadata.get("event_id", f"EVT-{hash(content) % 100000:05d}")
                timestamp = metadata.get("timestamp", "")

                self.connector.create_node(
                    "Event",
                    {
                        "event_id": event_id,
                        "event_type": "fault",
                        "timestamp": timestamp,
                        "station_id": station_id.upper() if station_id else "unknown",
                        "domain": "illigo",
                        "description": content[:300]
                    },
                    unique_key="event_id"
                )
                events_created += 1

                # Link event to station
                if station_id and station_id != "unknown":
                    self.connector.create_relationship(
                        "Event", "event_id", event_id,
                        "Station", "station_id", station_id.upper(),
                        "OCCURS_IN"
                    )

                # Extract error codes and create error nodes
                error_codes = re.findall(r'CX\d{3}', content)
                for error_code in set(error_codes):
                    self.connector.create_node(
                        "Error",
                        {
                            "error_code": error_code,
                            "domain": "illigo",
                            "severity": metadata.get("severity", "medium")
                        },
                        unique_key="error_code"
                    )
                    errors_created += 1

                    # Link event to error
                    self.connector.create_relationship(
                        "Event", "event_id", event_id,
                        "Error", "error_code", error_code,
                        "CAUSES"
                    )

        logger.info(
            f"Illigo ingestion complete: {stations_created} stations, "
            f"{events_created} events, {errors_created} errors"
        )

    def ingest_mri_failure_modes(self, failure_modes: List[Dict[str, Any]]):
        """
        Ingest MRI failure modes into the graph.

        Creates Fault nodes, Component nodes, and AFFECTS relationships.

        Args:
            failure_modes: List of failure mode dicts from failure_modes.csv
        """
        logger.info(f"Ingesting {len(failure_modes)} MRI failure modes")

        faults_created = 0
        components_created = 0

        for fm in failure_modes:
            fault_id = fm.get("failure_id", "")
            component_name = fm.get("component", "")

            # Create Fault node
            self.connector.create_node(
                "Fault",
                {
                    "fault_id": fault_id,
                    "failure_mode": fm.get("failure_mode", ""),
                    "severity": fm.get("severity", "medium"),
                    "component": component_name,
                    "symptom": fm.get("symptom", ""),
                    "root_cause": fm.get("root_cause", ""),
                    "detection_method": fm.get("detection_method", ""),
                    "mttr_hours": float(fm.get("mttr_hours", 0)),
                    "repair_action": fm.get("repair_action", ""),
                    "spare_parts": fm.get("spare_parts_required", ""),
                    "preventive_maintenance": fm.get("preventive_maintenance", ""),
                },
                unique_key="fault_id"
            )
            faults_created += 1

            # Create Component node
            if component_name:
                comp_id = f"COMP-{component_name.replace(' ', '-').upper()[:30]}"
                self.connector.create_node(
                    "Component",
                    {
                        "component_id": comp_id,
                        "name": component_name,
                        "type": self._infer_component_type(component_name),
                    },
                    unique_key="component_id"
                )
                components_created += 1

                # Create AFFECTS relationship
                self.connector.create_relationship(
                    "Fault", "fault_id", fault_id,
                    "Component", "component_id", comp_id,
                    "AFFECTS"
                )

        logger.info(
            f"MRI failure modes ingested: {faults_created} faults, "
            f"{components_created} components"
        )

    def ingest_mri_events(self, events: List[Dict[str, Any]], max_events: int = 1000):
        """
        Ingest MRI telemetry events into the graph.

        Creates Event nodes and links to Fault nodes when patterns match.

        Args:
            events: List of event dicts from mri_events.csv
            max_events: Maximum events to ingest (errors/warnings prioritized)
        """
        # Prioritize error and warning events
        priority_events = [e for e in events if e.get("severity") in ("error", "warning")]
        info_events = [e for e in events if e.get("severity") == "info"]
        selected = priority_events[:max_events]
        remaining = max_events - len(selected)
        if remaining > 0:
            selected += info_events[:remaining]

        logger.info(f"Ingesting {len(selected)} MRI events (from {len(events)} total)")

        events_created = 0
        for evt in selected:
            event_id = f"EVT-{evt.get('timestamp', '').replace(' ', '_').replace(':', '')[:20]}-{evt.get('event_id', '')}"
            self.connector.create_node(
                "Event",
                {
                    "event_id": event_id,
                    "timestamp": evt.get("timestamp", ""),
                    "level": evt.get("level", ""),
                    "source": evt.get("source", ""),
                    "event_id_raw": evt.get("event_id", ""),
                    "description": evt.get("description", "")[:300],
                    "is_mri_specific": evt.get("is_mri_specific", False),
                    "is_thermal": evt.get("is_thermal", False),
                },
                unique_key="event_id"
            )
            events_created += 1

            # Link thermal events to thermal fault
            if evt.get("is_thermal"):
                self.connector.create_relationship(
                    "Event", "event_id", event_id,
                    "Fault", "fault_id", "FM-001",
                    "TRIGGERS"
                )

        logger.info(f"MRI events ingested: {events_created} events")

    def ingest_clinical_protocols(self, protocols: List[Dict[str, Any]]):
        """
        Ingest clinical protocols and RadLex terms into the graph.

        Creates Protocol and RadLexTerm nodes.

        Args:
            protocols: List of protocol dicts from clinical_protocols.csv
        """
        logger.info(f"Ingesting {len(protocols)} clinical protocols")

        protocols_created = 0
        for proto in protocols:
            protocol_id = f"PROTO-{proto.get('filename', 'unknown')[:50]}"
            self.connector.create_node(
                "Protocol",
                {
                    "protocol_id": protocol_id,
                    "title": proto.get("title", ""),
                    "modality": proto.get("modality", "Other"),
                    "body_region": proto.get("body_region", "General"),
                    "description": proto.get("description", "")[:200],
                    "language": proto.get("language", "en"),
                },
                unique_key="protocol_id"
            )
            protocols_created += 1

        logger.info(f"Clinical protocols ingested: {protocols_created} protocols")

    def ingest_radlex_terms(self, terms: List[Dict[str, Any]]):
        """
        Ingest RadLex ontology terms and link to protocols.

        Args:
            terms: List of term dicts from radlex_terms.csv
        """
        logger.info(f"Ingesting {len(terms)} RadLex terms")

        terms_created = 0
        for term in terms:
            code = term.get("code", "")
            if not code:
                continue

            self.connector.create_node(
                "RadLexTerm",
                {
                    "code": code,
                    "meaning": term.get("meaning", ""),
                },
                unique_key="code"
            )
            terms_created += 1

            # Link to protocol
            template = term.get("template", "")
            if template:
                protocol_id = f"PROTO-{template[:50]}"
                self.connector.create_relationship(
                    "Protocol", "protocol_id", protocol_id,
                    "RadLexTerm", "code", code,
                    "USES_TERM"
                )

        logger.info(f"RadLex terms ingested: {terms_created} terms")

    def _infer_component_type(self, component_name: str) -> str:
        """Infer component type from name."""
        name_lower = component_name.lower()
        if any(w in name_lower for w in ["coil", "gradient", "rf"]):
            return "electromagnetic"
        elif any(w in name_lower for w in ["sensor", "temperature", "thermal"]):
            return "sensor"
        elif any(w in name_lower for w in ["compressor", "cryostat", "helium", "cold head"]):
            return "cryogenic"
        elif any(w in name_lower for w in ["table", "motor", "lock", "valve"]):
            return "mechanical"
        elif any(w in name_lower for w in ["software", "syngo", "application", "controller"]):
            return "software"
        elif any(w in name_lower for w in ["network", "dicom"]):
            return "network"
        elif any(w in name_lower for w in ["power", "psu", "amplifier"]):
            return "electrical"
        else:
            return "general"

    def query_faults_by_component(self, component_type: str) -> List[Dict[str, Any]]:
        """
        Query faults affecting a specific component type.

        Args:
            component_type: Component type (e.g., "sensor", "electromagnetic")

        Returns:
            List of faults affecting that component type
        """
        query = """
        MATCH (f:Fault)-[:AFFECTS]->(c:Component)
        WHERE toLower(c.type) = toLower($component_type)
           OR toLower(c.name) CONTAINS toLower($component_type)
        RETURN f.fault_id as fault_id,
               f.failure_mode as failure_mode,
               f.severity as severity,
               f.symptom as symptom,
               f.root_cause as root_cause,
               f.repair_action as repair_action,
               c.name as component_name,
               c.type as component_type
        """
        return self.connector.execute_query(query, {"component_type": component_type})

    def query_faults_by_severity(self, severity: str) -> List[Dict[str, Any]]:
        """
        Query faults by severity level.

        Args:
            severity: Severity level (critical, high, medium, low)
        """
        query = """
        MATCH (f:Fault)
        WHERE toLower(f.severity) = toLower($severity)
        RETURN f.fault_id as fault_id,
               f.failure_mode as failure_mode,
               f.severity as severity,
               f.component as component,
               f.symptom as symptom,
               f.root_cause as root_cause,
               f.repair_action as repair_action,
               f.mttr_hours as mttr_hours
        ORDER BY f.mttr_hours DESC
        """
        return self.connector.execute_query(query, {"severity": severity})

    def query_fault_by_symptom(self, symptom_keywords: str) -> List[Dict[str, Any]]:
        """
        Find faults matching symptom keywords.

        Args:
            symptom_keywords: Keywords from symptom description

        Returns:
            Matching faults with details
        """
        query = """
        MATCH (f:Fault)
        WHERE toLower(f.symptom) CONTAINS toLower($keywords)
           OR toLower(f.failure_mode) CONTAINS toLower($keywords)
           OR toLower(f.root_cause) CONTAINS toLower($keywords)
        RETURN f.fault_id as fault_id,
               f.failure_mode as failure_mode,
               f.severity as severity,
               f.component as component,
               f.symptom as symptom,
               f.root_cause as root_cause,
               f.repair_action as repair_action
        LIMIT 5
        """
        return self.connector.execute_query(query, {"keywords": symptom_keywords})

    def query_protocols_by_modality(self, modality: str) -> List[Dict[str, Any]]:
        """Query clinical protocols by modality (CT, MRI, etc.)."""
        query = """
        MATCH (p:Protocol)
        WHERE toLower(p.modality) = toLower($modality)
        RETURN p.protocol_id as protocol_id,
               p.title as title,
               p.modality as modality,
               p.body_region as body_region
        LIMIT 20
        """
        return self.connector.execute_query(query, {"modality": modality})

    def _infer_severity(self, content: str) -> str:
        """Infer severity from content text."""
        content_lower = content.lower()
        if any(word in content_lower for word in ["critical", "emergency", "urgent"]):
            return "critical"
        elif any(word in content_lower for word in ["high", "severe", "serious"]):
            return "high"
        elif any(word in content_lower for word in ["medium", "moderate"]):
            return "medium"
        else:
            return "low"

    def build_graph(
        self,
        telekom_data: List[Dict[str, Any]] = None,
        siemens_data: List[Dict[str, Any]] = None,
        illigo_data: List[Dict[str, Any]] = None,
        clear_existing: bool = False
    ):
        """
        Build the complete Knowledge Graph from all data sources.

        Args:
            telekom_data: Processed Telekom/governance documents
            siemens_data: Processed Siemens/hardware scans
            illigo_data: Processed Illigo/telemetry events
            clear_existing: Whether to delete existing graph data
        """
        logger.info("Building Knowledge Graph from tripartite data")

        if clear_existing:
            logger.warning("Clearing existing graph data")
            self.connector.delete_all()

        # Create schema
        self.create_schema()

        # Ingest data from all domains (legacy methods)
        if telekom_data:
            self.ingest_telekom_data(telekom_data)
        if siemens_data:
            self.ingest_siemens_data(siemens_data)
        if illigo_data:
            self.ingest_illigo_data(illigo_data)

        # Log final stats
        stats = self.connector.get_stats()
        logger.info(f"Knowledge Graph construction complete: {stats}")

        return stats

    def build_mri_graph(
        self,
        failure_modes: List[Dict[str, Any]] = None,
        events: List[Dict[str, Any]] = None,
        protocols: List[Dict[str, Any]] = None,
        radlex_terms: List[Dict[str, Any]] = None,
        clear_existing: bool = False
    ):
        """
        Build the MRI Healthcare Knowledge Graph from processed data.

        Args:
            failure_modes: From data/processed/telemetry/failure_modes.csv
            events: From data/processed/telemetry/mri_events.csv
            protocols: From data/processed/governance/clinical_protocols.csv
            radlex_terms: From data/processed/governance/radlex_terms.csv
            clear_existing: Whether to delete existing graph data
        """
        logger.info("Building MRI Healthcare Knowledge Graph")

        if clear_existing:
            logger.warning("Clearing existing graph data")
            self.connector.delete_all()

        self.create_schema()

        if failure_modes:
            self.ingest_mri_failure_modes(failure_modes)
        if events:
            self.ingest_mri_events(events)
        if protocols:
            self.ingest_clinical_protocols(protocols)
        if radlex_terms:
            self.ingest_radlex_terms(radlex_terms)

        stats = self.connector.get_stats()
        logger.info(f"MRI Knowledge Graph construction complete: {stats}")
        return stats

    def query_fault_path(self, error_code: str) -> List[Dict[str, Any]]:
        """
        Query the graph to find diagnostic path for a given error.

        Finds the error, related events, affected devices/stations,
        and resolution procedures.

        Args:
            error_code: Error code to diagnose (e.g., "CX002")

        Returns:
            List of related entities and procedures
        """
        query = """
        MATCH (e:Error {error_code: $error_code})
        OPTIONAL MATCH (e)<-[:CAUSES]-(evt:Event)
        OPTIONAL MATCH (evt)-[:OCCURS_IN]->(s:Station)
        OPTIONAL MATCH (p:Procedure)-[:RESOLVES]->(e)
        OPTIONAL MATCH (e)-[:VIOLATES]->(sla:SLA)
        RETURN
            e.error_code as error_code,
            e.severity as severity,
            e.domain as domain,
            collect(DISTINCT {
                event_id: evt.event_id,
                timestamp: evt.timestamp,
                event_type: evt.event_type
            }) as related_events,
            collect(DISTINCT {
                station_id: s.station_id,
                location: s.location
            }) as affected_stations,
            collect(DISTINCT {
                procedure_id: p.procedure_id,
                description: p.description
            }) as resolution_procedures,
            collect(DISTINCT sla.sla_id) as violated_slas
        """

        results = self.connector.execute_query(query, {"error_code": error_code})
        return results

    def query_station_history(self, station_id: str) -> List[Dict[str, Any]]:
        """
        Query events and errors for a specific station.

        Args:
            station_id: Station identifier (e.g., "KOUMASSI")

        Returns:
            List of events at the station
        """
        query = """
        MATCH (s:Station {station_id: $station_id})
        OPTIONAL MATCH (evt:Event)-[:OCCURS_IN]->(s)
        OPTIONAL MATCH (evt)-[:CAUSES]->(e:Error)
        RETURN
            s.station_id as station_id,
            s.location as location,
            collect({
                event_id: evt.event_id,
                timestamp: evt.timestamp,
                event_type: evt.event_type,
                error_code: e.error_code,
                severity: e.severity
            }) as events
        ORDER BY evt.timestamp DESC
        """

        results = self.connector.execute_query(query, {"station_id": station_id.upper()})
        return results

    def find_related_errors(self, error_code: str) -> List[Dict[str, Any]]:
        """
        Find errors that are related (co-occur or have causal links).

        Args:
            error_code: Starting error code

        Returns:
            List of related errors
        """
        query = """
        MATCH (e1:Error {error_code: $error_code})
        OPTIONAL MATCH (e1)<-[:CAUSES]-(evt:Event)-[:CAUSES]->(e2:Error)
        WHERE e1 <> e2
        OPTIONAL MATCH (e1)-[:RELATED_TO]-(e3:Error)
        WITH e1, collect(DISTINCT e2) + collect(DISTINCT e3) as related
        UNWIND related as e
        WHERE e IS NOT NULL
        RETURN DISTINCT
            e.error_code as error_code,
            e.severity as severity,
            e.domain as domain
        """

        results = self.connector.execute_query(query, {"error_code": error_code})
        return results


def main():
    """Build the MRI Healthcare Knowledge Graph from processed data."""
    import csv
    import sys
    sys.path.insert(0, str(project_root))

    print("=" * 60)
    print("MRI Healthcare Knowledge Graph Builder")
    print("=" * 60)

    data_dir = project_root / "data" / "processed"

    # Load failure modes
    failure_modes = []
    fm_path = data_dir / "telemetry" / "failure_modes.csv"
    if fm_path.exists():
        with open(fm_path, 'r', encoding='utf-8') as f:
            failure_modes = list(csv.DictReader(f))
    print(f"Failure modes: {len(failure_modes)}")

    # Load events (sample for graph - full dataset is too large)
    events = []
    events_path = data_dir / "telemetry" / "mri_events.csv"
    if events_path.exists():
        with open(events_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                events.append(row)
                if i >= 5000:  # Limit for graph ingestion
                    break
    print(f"Events (sampled): {len(events)}")

    # Load protocols
    protocols = []
    proto_path = data_dir / "governance" / "clinical_protocols.csv"
    if proto_path.exists():
        with open(proto_path, 'r', encoding='utf-8') as f:
            protocols = list(csv.DictReader(f))
    print(f"Protocols: {len(protocols)}")

    # Load RadLex terms
    radlex_terms = []
    radlex_path = data_dir / "governance" / "radlex_terms.csv"
    if radlex_path.exists():
        with open(radlex_path, 'r', encoding='utf-8') as f:
            radlex_terms = list(csv.DictReader(f))
    print(f"RadLex terms: {len(radlex_terms)}")

    try:
        print("\nConnecting to Neo4j...")
        with Neo4jConnector() as connector:
            builder = GraphBuilder(connector)

            print("Building MRI Knowledge Graph...")
            stats = builder.build_mri_graph(
                failure_modes=failure_modes,
                events=events,
                protocols=protocols,
                radlex_terms=radlex_terms,
                clear_existing=True
            )

            print(f"\nGraph built successfully!")
            print(f"Nodes: {stats['nodes']}")
            print(f"Relationships: {stats['relationships']}")

            # Test MRI queries
            print("\nTesting fault query for thermal components...")
            results = builder.query_faults_by_component("sensor")
            if results:
                for r in results[:3]:
                    print(f"  {r['fault_id']}: {r['failure_mode']} ({r['severity']})")
            else:
                print("  No results found")

            print("\nTesting critical fault query...")
            results = builder.query_faults_by_severity("critical")
            if results:
                for r in results[:3]:
                    print(f"  {r['fault_id']}: {r['failure_mode']} - MTTR: {r['mttr_hours']}h")

    except ValueError as e:
        print(f"\nNeo4j connection not configured: {e}")
        print("Set NEO4J_PASSWORD in your environment or config/.env")
        print("\nTo start Neo4j with Docker:")
        print("  docker run -p7474:7474 -p7687:7687 -e NEO4J_AUTH=neo4j/password neo4j")


if __name__ == "__main__":
    main()
