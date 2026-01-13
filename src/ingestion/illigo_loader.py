"""
Illigo Loader - RAG Ingestion Layer

Processes Illigo charging station data for RAG-based fault diagnosis:
1. Extracts baseline performance metrics from PDF statistics
2. Generates mock fault event logs for thesis scenarios

Purpose:
- Establish 'Normal' baseline from PDF statistics
- Create 'Abnormal' fault events for diagnosis scenarios
- Enable RAG queries like "What caused the ground fault at Koumassi?"

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import logging
from langchain_core.documents import Document

# Try to import pypdf, fallback to PyPDF2
try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IlligoLoader:
    """Loads Illigo charging station data and generates mock fault scenarios."""

    def __init__(
        self,
        pdf_path: str = "data/raw/illigo/data/statistique_export_2025-08-31_au_2026-01-11.pdf"
    ):
        """
        Initialize the Illigo loader.

        Args:
            pdf_path: Path to the statistics PDF file
        """
        self.pdf_path = Path(pdf_path)

    def extract_pdf_text(self) -> str:
        """
        Extract text from the Illigo statistics PDF.

        Returns:
            Full text extracted from PDF
        """
        logger.info(f"Extracting text from PDF: {self.pdf_path}")

        if not self.pdf_path.exists():
            logger.error(f"PDF file not found: {self.pdf_path}")
            raise FileNotFoundError(f"PDF file not found: {self.pdf_path}")

        try:
            reader = PdfReader(str(self.pdf_path))
            text_content = []

            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text:
                    text_content.append(f"--- Page {page_num} ---\n{text}")

            full_text = "\n\n".join(text_content)
            logger.info(f"Extracted {len(full_text)} characters from {len(reader.pages)} pages")

            return full_text

        except Exception as e:
            logger.error(f"Error extracting PDF text: {str(e)}")
            raise

    def generate_mock_fault_logs(self) -> List[Dict[str, Any]]:
        """
        Generate mock OCPP fault event logs for thesis scenarios.

        This creates realistic fault events that can be used for RAG-based
        fault diagnosis testing.

        Returns:
            List of fault event dictionaries
        """
        logger.info("Generating mock fault logs")

        fault_events = [
            # Primary fault event as specified
            {
                "event_id": "EVT_001",
                "station_id": "Petro Ivoire KOUMASSI",
                "station_code": "KOUMASSI",
                "timestamp": "2026-01-15T14:22:00",
                "event_type": "FaultNotification",
                "fault_code": "CX002",
                "fault_name": "Ground Fault",
                "severity": "High",
                "description": "Ground fault detected at charging connector. Charging session terminated for safety.",
                "connector_id": 1,
                "vendor_error_code": "GND_FAULT_001",
                "info": "Insulation resistance below threshold (< 100 Ohm)",
                "ocpp_version": "2.0.1",
                "status": "Faulted"
            },
            # Supporting event: Status change before fault
            {
                "event_id": "EVT_002",
                "station_id": "Petro Ivoire KOUMASSI",
                "station_code": "KOUMASSI",
                "timestamp": "2026-01-15T14:21:45",
                "event_type": "StatusNotification",
                "fault_code": None,
                "fault_name": None,
                "severity": "Info",
                "description": "Connector status changed to Charging",
                "connector_id": 1,
                "vendor_error_code": None,
                "info": "Vehicle connected, charging session started",
                "ocpp_version": "2.0.1",
                "status": "Charging"
            },
            # Supporting event: Station was operational before
            {
                "event_id": "EVT_003",
                "station_id": "Petro Ivoire KOUMASSI",
                "station_code": "KOUMASSI",
                "timestamp": "2026-01-15T09:00:00",
                "event_type": "BootNotification",
                "fault_code": None,
                "fault_name": None,
                "severity": "Info",
                "description": "Charging station booted successfully",
                "connector_id": None,
                "vendor_error_code": None,
                "info": "Station online and ready for service",
                "ocpp_version": "2.0.1",
                "status": "Available"
            },
            # Additional fault at ANGRÉ for comparison
            {
                "event_id": "EVT_004",
                "station_id": "Petro Ivoire ANGRÉ",
                "station_code": "ANGRÉ",
                "timestamp": "2026-01-16T10:15:30",
                "event_type": "FaultNotification",
                "fault_code": "CX003",
                "fault_name": "Over Current",
                "severity": "Medium",
                "description": "Over current detected, charging limited to 80%",
                "connector_id": 2,
                "vendor_error_code": "OC_LIMIT_002",
                "info": "Current exceeded 32A threshold, reduced to 25A",
                "ocpp_version": "2.0.1",
                "status": "Charging"
            }
        ]

        logger.info(f"Generated {len(fault_events)} mock fault events")
        return fault_events

    def load(self) -> List[Document]:
        """
        Load Illigo data: PDF statistics + mock fault logs.

        Returns:
            List of LangChain Documents (baseline stats + fault events)
        """
        logger.info("Loading Illigo charging station data")

        documents = []

        # Task A: Load PDF statistics (baseline/normal context)
        try:
            pdf_text = self.extract_pdf_text()

            # Create document for PDF statistics
            pdf_doc = Document(
                page_content=f"ILLIGO CHARGING STATION STATISTICS - BASELINE PERFORMANCE\n\n{pdf_text}",
                metadata={
                    'source': 'illigo_statistics',
                    'data_type': 'baseline_performance',
                    'period': '2025-08-31 to 2026-01-11',
                    'file_name': self.pdf_path.name,
                    'content_type': 'pdf_statistics'
                }
            )
            documents.append(pdf_doc)
            logger.info("Added PDF statistics document")

        except Exception as e:
            logger.warning(f"Could not load PDF statistics: {str(e)}")

        # Task B: Generate mock fault logs (abnormal events)
        fault_events = self.generate_mock_fault_logs()

        for event in fault_events:
            # Convert event to natural language description
            event_text = self._fault_event_to_text(event)

            # Create document for each fault event
            fault_doc = Document(
                page_content=event_text,
                metadata={
                    'source': 'illigo_fault_logs',
                    'data_type': 'fault_event',
                    'event_id': event['event_id'],
                    'station_id': event['station_code'],
                    'timestamp': event['timestamp'],
                    'fault_code': event.get('fault_code'),
                    'severity': event['severity'],
                    'event_type': event['event_type'],
                    'content_type': 'ocpp_event',
                    'raw_event': json.dumps(event)
                }
            )
            documents.append(fault_doc)

        logger.info(f"Created {len(documents)} total documents ({len(fault_events)} fault events)")
        return documents

    def _fault_event_to_text(self, event: Dict[str, Any]) -> str:
        """
        Convert a fault event dictionary to natural language.

        Args:
            event: Fault event dictionary

        Returns:
            Natural language description
        """
        station = event['station_id']
        timestamp = event['timestamp']
        event_type = event['event_type']
        description = event['description']

        text_parts = [
            f"Charging Station: {station}",
            f"Timestamp: {timestamp}",
            f"Event Type: {event_type}",
            f"Description: {description}"
        ]

        if event.get('fault_code'):
            text_parts.append(f"Fault Code: {event['fault_code']} ({event['fault_name']})")
            text_parts.append(f"Severity: {event['severity']}")

        if event.get('info'):
            text_parts.append(f"Additional Info: {event['info']}")

        if event.get('connector_id'):
            text_parts.append(f"Connector ID: {event['connector_id']}")

        return ". ".join(text_parts) + "."


def main():
    """Test the Illigo loader."""
    logger.info("=" * 60)
    logger.info("Testing Illigo Loader")
    logger.info("=" * 60)

    try:
        loader = IlligoLoader()
        documents = loader.load()

        logger.info(f"\nSuccessfully loaded {len(documents)} documents")

        # Display statistics document
        if documents:
            logger.info("\n" + "=" * 60)
            logger.info("BASELINE STATISTICS DOCUMENT (Truncated):")
            logger.info("=" * 60)
            content = documents[0].page_content
            print(f"\nContent (first 500 chars):\n{content[:500]}...\n")
            print(f"Metadata:\n{documents[0].metadata}\n")

        # Display fault event document
        if len(documents) > 1:
            logger.info("\n" + "=" * 60)
            logger.info("FAULT EVENT DOCUMENT (Ground Fault at KOUMASSI):")
            logger.info("=" * 60)
            print(f"\nContent:\n{documents[1].page_content}\n")
            print(f"Metadata:\n{documents[1].metadata}\n")

        # Display all fault events summary
        fault_docs = [d for d in documents if d.metadata.get('data_type') == 'fault_event']
        logger.info("\n" + "=" * 60)
        logger.info(f"SUMMARY: {len(fault_docs)} FAULT EVENTS GENERATED")
        logger.info("=" * 60)
        for doc in fault_docs:
            print(f"  - {doc.metadata['event_id']}: {doc.metadata['station_id']} - {doc.metadata['fault_code']} ({doc.metadata['severity']})")

        logger.info("\n" + "=" * 60)
        logger.info("Test completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
