"""
Graph Service - Shared Knowledge Graph Access for All Agents

Provides a clean interface to Neo4j knowledge graph queries.
Agents can use this to enhance their RAG context with graph-based reasoning.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import os
import re
import logging
import threading
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class GraphService:
    """
    Shared service for knowledge graph queries.

    Wraps the GraphBuilder to provide agent-friendly methods
    for retrieving graph context during reasoning.
    """

    def __init__(self):
        """Initialize the graph service with Neo4j connection."""
        self._builder = None
        self._initialized = False
        self._init_error = None

    def _lazy_init(self) -> bool:
        """Lazily initialize the graph builder on first use."""
        if self._initialized:
            return self._builder is not None

        try:
            from src.graph.neo4j_connector import Neo4jConnector
            from src.graph.graph_builder import GraphBuilder

            # Create and connect to Neo4j
            connector = Neo4jConnector()
            connector.connect()

            # Create graph builder with the connector
            self._builder = GraphBuilder(connector)
            self._initialized = True
            logger.info("GraphService initialized successfully with Neo4j connection")
            return True
        except Exception as e:
            self._init_error = str(e)
            self._initialized = True
            logger.warning(f"GraphService initialization failed: {e}")
            return False

    def is_available(self) -> bool:
        """Check if the graph service is available."""
        return self._lazy_init()

    def get_fault_context(self, error_code: str) -> Optional[Dict[str, Any]]:
        """
        Query the graph for fault diagnosis context.

        Args:
            error_code: Error code to look up (e.g., "CX002")

        Returns:
            Dict with fault path including:
            - error_code, severity, domain
            - related_events
            - affected_stations
            - resolution_procedures
            - violated_slas
        """
        if not self._lazy_init():
            return None

        try:
            results = self._builder.query_fault_path(error_code)
            if results and len(results) > 0:
                # Return first result (should be unique by error_code)
                result = results[0]
                # Filter out empty collections
                return {
                    k: v for k, v in result.items()
                    if v and (not isinstance(v, list) or len(v) > 0)
                }
            return None
        except Exception as e:
            logger.error(f"Error querying fault path for {error_code}: {e}")
            return None

    def get_station_history(self, station_id: str) -> Optional[Dict[str, Any]]:
        """
        Query the graph for station event history.

        Args:
            station_id: Station identifier (e.g., "KOUMASSI")

        Returns:
            Dict with station history including events and errors
        """
        if not self._lazy_init():
            return None

        try:
            results = self._builder.query_station_history(station_id)
            if results and len(results) > 0:
                result = results[0]
                # Filter out empty events
                events = result.get('events', [])
                filtered_events = [
                    e for e in events
                    if e.get('event_id') or e.get('error_code')
                ]
                if filtered_events:
                    return {
                        'station_id': result.get('station_id'),
                        'location': result.get('location'),
                        'events': filtered_events[:10]  # Limit to recent 10
                    }
            return None
        except Exception as e:
            logger.error(f"Error querying station history for {station_id}: {e}")
            return None

    def find_related_errors(self, error_code: str) -> List[Dict[str, Any]]:
        """
        Find errors that are causally related or co-occur.

        Args:
            error_code: Starting error code

        Returns:
            List of related errors with severity and domain
        """
        if not self._lazy_init():
            return []

        try:
            results = self._builder.find_related_errors(error_code)
            return results if results else []
        except Exception as e:
            logger.error(f"Error finding related errors for {error_code}: {e}")
            return []

    def extract_error_codes(self, text: str) -> List[str]:
        """
        Extract error codes from text using regex patterns.

        Supports patterns like:
        - FM-001 (MRI failure mode IDs)
        - CX001, CX002 (Legacy charging station errors)
        - ERR-001, ERR-002 (Generic)

        Args:
            text: Text to search for error codes

        Returns:
            List of unique error codes found
        """
        patterns = [
            r'FM[-_]?\d{3}',      # MRI failure mode IDs (FM-001, FM001)
            r'CX\d{3}',           # Legacy charging station errors
            r'ERR[-_]?\d{3}',     # Generic errors (ERR-001, ERR001)
            r'FAULT[-_]?\d{3}',   # Fault codes
        ]

        error_codes = set()
        for pattern in patterns:
            matches = re.findall(pattern, text.upper())
            error_codes.update(matches)

        return list(error_codes)

    def extract_symptom_keywords(self, text: str) -> List[str]:
        """
        Extract MRI-relevant symptom keywords from query text.

        Args:
            text: Query text to analyze

        Returns:
            List of relevant keywords for graph lookup
        """
        mri_keywords = [
            'thermal', 'temperature', 'shutdown', 'overheat', 'cooling',
            'gradient', 'coil', 'degradation', 'artifact',
            'helium', 'quench', 'cryogen', 'compressor',
            'rf amplifier', 'signal', 'snr', 'noise',
            'table', 'positioning', 'alignment',
            'dicom', 'network', 'pacs', 'transfer',
            'shimming', 'b0', 'homogeneity',
            'reconstruction', 'timeout', 'queue',
            'interlock', 'door', 'safety',
            'protocol', 'sequence', 'scan',
            'calibration', 'drift', 'sensor',
            'power', 'ups', 'supply',
            'sar', 'ecg', 'gating',
        ]

        text_lower = text.lower()
        found = [kw for kw in mri_keywords if kw in text_lower]
        return found

    def get_fault_context_by_symptom(self, symptom: str) -> Optional[List[Dict[str, Any]]]:
        """
        Query graph for faults matching symptom keywords.

        Args:
            symptom: Symptom description text

        Returns:
            List of matching fault records
        """
        if not self._lazy_init():
            return None

        try:
            keywords = self.extract_symptom_keywords(symptom)
            results = []
            for keyword in keywords[:3]:  # Limit to top 3 keywords
                matches = self._builder.query_fault_by_symptom(keyword)
                results.extend(matches)

            # Deduplicate by fault_id
            seen = set()
            unique = []
            for r in results:
                fid = r.get('fault_id', '')
                if fid not in seen:
                    seen.add(fid)
                    unique.append(r)

            return unique[:5] if unique else None
        except Exception as e:
            logger.error(f"Error querying faults by symptom: {e}")
            return None

    def get_enriched_context(
        self,
        query: str,
        location: Optional[str] = None
    ) -> str:
        """
        Get graph-enriched context for a query.

        Extracts fault IDs, symptom keywords, and component references,
        then queries the graph and returns formatted context.

        Args:
            query: User query text
            location: Optional location hint

        Returns:
            Formatted string with graph knowledge
        """
        context_parts = []

        # 1. Extract and query explicit fault/error codes
        error_codes = self.extract_error_codes(query)
        for code in error_codes:
            fault_info = self.get_fault_context(code)
            if fault_info:
                context_parts.append(
                    f"[Graph - Error {code}]: "
                    f"Severity={fault_info.get('severity', 'unknown')}, "
                    f"Domain={fault_info.get('domain', 'unknown')}"
                )

                procedures = fault_info.get('resolution_procedures', [])
                if procedures:
                    proc_str = "; ".join([
                        p.get('description', 'Unknown procedure')[:100]
                        for p in procedures[:3]
                    ])
                    context_parts.append(f"[Graph - Procedures]: {proc_str}")

                slas = fault_info.get('violated_slas', [])
                if slas:
                    context_parts.append(f"[Graph - Violated SLAs]: {', '.join(slas)}")

            related = self.find_related_errors(code)
            if related:
                related_str = ", ".join([
                    f"{r.get('error_code')}({r.get('severity', '?')})"
                    for r in related[:5]
                ])
                context_parts.append(f"[Graph - Related Errors]: {related_str}")

        # 2. Symptom-based fault lookup (MRI-specific)
        symptom_faults = self.get_fault_context_by_symptom(query)
        if symptom_faults:
            context_parts.append("[Graph - Matching MRI Fault Modes]:")
            for fault in symptom_faults[:3]:
                context_parts.append(
                    f"  {fault.get('fault_id', '?')}: {fault.get('failure_mode', '?')} "
                    f"({fault.get('severity', '?')}) - "
                    f"Component: {fault.get('component', '?')}, "
                    f"Root cause: {fault.get('root_cause', '?')[:100]}"
                )
                repair = fault.get('repair_action', '')
                if repair:
                    context_parts.append(f"    Repair: {repair[:150]}")

        # 3. Legacy station history queries
        stations = []
        if location:
            stations.append(location.upper())

        for station in stations[:2]:
            history = self.get_station_history(station)
            if history:
                events = history.get('events', [])
                if events:
                    event_summary = "; ".join([
                        f"{e.get('event_type', 'event')}@{e.get('timestamp', '?')}"
                        for e in events[:5]
                    ])
                    context_parts.append(
                        f"[Graph - Station {station} History]: {event_summary}"
                    )

        if context_parts:
            return "\n".join(context_parts)
        return ""


# Singleton instance for sharing across agents (thread-safe)
_graph_service_instance = None
_graph_service_lock = threading.Lock()


def get_graph_service() -> GraphService:
    """
    Get or create the singleton GraphService instance.

    Uses double-checked locking pattern for thread safety.
    """
    global _graph_service_instance
    if _graph_service_instance is None:
        with _graph_service_lock:
            # Double-check after acquiring lock
            if _graph_service_instance is None:
                _graph_service_instance = GraphService()
    return _graph_service_instance
