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

    # Define graph schema
    NODE_LABELS = {
        "Device": ["device_id", "name", "type", "manufacturer", "location"],
        "Error": ["error_code", "description", "severity", "domain"],
        "Procedure": ["procedure_id", "name", "steps", "domain"],
        "Event": ["event_id", "timestamp", "event_type", "station_id"],
        "Hardware": ["hardware_id", "model", "manufacturer", "institution"],
        "Station": ["station_id", "name", "location", "connector_count"],
        "SLA": ["sla_id", "name", "metric", "threshold", "domain"],
    }

    RELATIONSHIP_TYPES = {
        "CAUSES": "Error or Event causes another Error or Event",
        "RESOLVES": "Procedure resolves an Error",
        "OCCURS_IN": "Error or Event occurs in a Device or Station",
        "DETECTED_BY": "Error was detected by Hardware scan",
        "FOLLOWS": "Event follows another Event in sequence",
        "REQUIRES": "Procedure requires a specific Hardware or Device",
        "VIOLATES": "Event or Error violates an SLA",
        "HAS_HARDWARE": "Station or Institution has Hardware",
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
            ("Device", "device_id"),
            ("Error", "error_code"),
            ("Procedure", "procedure_id"),
            ("Event", "event_id"),
            ("Hardware", "hardware_id"),
            ("Station", "station_id"),
            ("SLA", "sla_id"),
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
            ("Device", "type"),
            ("Device", "location"),
            ("Error", "severity"),
            ("Error", "domain"),
            ("Event", "timestamp"),
            ("Event", "event_type"),
            ("Station", "location"),
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
        telekom_data: List[Dict[str, Any]],
        siemens_data: List[Dict[str, Any]],
        illigo_data: List[Dict[str, Any]],
        clear_existing: bool = False
    ):
        """
        Build the complete Knowledge Graph from all data sources.

        Args:
            telekom_data: Processed Telekom documents
            siemens_data: Processed Siemens scans
            illigo_data: Processed Illigo events
            clear_existing: Whether to delete existing graph data
        """
        logger.info("Building Knowledge Graph from tripartite data")

        if clear_existing:
            logger.warning("Clearing existing graph data")
            self.connector.delete_all()

        # Create schema
        self.create_schema()

        # Ingest data from all domains
        self.ingest_telekom_data(telekom_data)
        self.ingest_siemens_data(siemens_data)
        self.ingest_illigo_data(illigo_data)

        # Log final stats
        stats = self.connector.get_stats()
        logger.info(f"Knowledge Graph construction complete: {stats}")

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
    """Example usage of the graph builder."""
    import sys
    sys.path.insert(0, str(project_root))

    from src.agents.telekom_minister.data_loader import TelekomLoader
    from src.agents.siemens_technician.data_loader import SiemensLoader
    from src.agents.illigo_operator.data_loader import IlligoLoader

    print("=" * 60)
    print("Knowledge Graph Builder")
    print("=" * 60)

    # Load data from all sources
    print("\nLoading data...")
    telekom_loader = TelekomLoader()
    siemens_loader = SiemensLoader()
    illigo_loader = IlligoLoader()

    telekom_docs = telekom_loader.load()
    siemens_docs = siemens_loader.load()
    illigo_docs = illigo_loader.load()

    print(f"Telekom docs: {len(telekom_docs)}")
    print(f"Siemens docs: {len(siemens_docs)}")
    print(f"Illigo docs: {len(illigo_docs)}")

    # Convert LangChain documents to dicts
    def docs_to_dicts(docs):
        return [
            {"content": d.page_content, "metadata": d.metadata}
            for d in docs
        ]

    try:
        print("\nConnecting to Neo4j...")
        with Neo4jConnector() as connector:
            builder = GraphBuilder(connector)

            print("Building graph...")
            stats = builder.build_graph(
                docs_to_dicts(telekom_docs),
                docs_to_dicts(siemens_docs),
                docs_to_dicts(illigo_docs),
                clear_existing=True
            )

            print(f"\nGraph built successfully!")
            print(f"Nodes: {stats['nodes']}")
            print(f"Relationships: {stats['relationships']}")

            # Test query
            print("\nTesting fault path query for CX002...")
            results = builder.query_fault_path("CX002")
            if results:
                print(f"Found: {results}")
            else:
                print("No results found for CX002")

    except ValueError as e:
        print(f"\nNeo4j connection not configured: {e}")
        print("Set NEO4J_PASSWORD in your environment or config/.env")
        print("\nTo start Neo4j with Docker:")
        print("  docker run -p7474:7474 -p7687:7687 -e NEO4J_AUTH=neo4j/password neo4j")


if __name__ == "__main__":
    main()
