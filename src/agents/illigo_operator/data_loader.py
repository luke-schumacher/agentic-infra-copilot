"""
Illigo Operator Data Loader

Processes Illigo charging station data for RAG-based fault diagnosis:
1. Extracts baseline performance metrics from PDF statistics
2. Loads session data and station metadata from CSV files
3. Generates mock fault event logs for thesis scenarios

Migrated from src/ingestion/illigo_loader.py for agent-specific ownership.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from langchain_core.documents import Document

# Try to import pypdf, fallback to PyPDF2
try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    try:
        from PyPDF2 import PdfReader
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IlligoLoader:
    """Loads Illigo charging station data for the Operator agent."""

    def __init__(
        self,
        data_dir: str = "data/raw/illigo/data",
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        Initialize the Illigo loader.

        Args:
            data_dir: Directory containing Illigo data files
            chunk_size: Size of text chunks for PDF splitting
            chunk_overlap: Overlap between chunks
        """
        self.data_dir = Path(data_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_pdf_text(self, pdf_path: Path) -> str:
        """
        Extract text from a PDF file.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Full text extracted from PDF
        """
        if not PDF_AVAILABLE:
            logger.warning("PDF library not available. Skipping PDF extraction.")
            return ""

        logger.info(f"Extracting text from PDF: {pdf_path}")

        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return ""

        try:
            reader = PdfReader(str(pdf_path))
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
            return ""

    def load_sessions_csv(self) -> List[Document]:
        """
        Load charging sessions data from CSV.

        Returns:
            List of Document objects with session data
        """
        csv_path = self.data_dir / "sessions_toutes-dates.csv"

        if not csv_path.exists():
            logger.warning(f"Sessions CSV not found: {csv_path}")
            return []

        logger.info(f"Loading sessions CSV: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8', on_bad_lines='warn')
            logger.info(f"Loaded {len(df)} session records")

            documents = []

            # Create summary document
            summary_text = self._create_sessions_summary(df)
            summary_doc = Document(
                page_content=summary_text,
                metadata={
                    'source_type': 'illigo_sessions',
                    'data_type': 'session_summary',
                    'record_count': len(df),
                    'file_name': csv_path.name,
                    'agent': 'illigo_operator'
                }
            )
            documents.append(summary_doc)

            # Create documents for station-level aggregations
            if 'station' in df.columns or 'station_id' in df.columns:
                station_col = 'station' if 'station' in df.columns else 'station_id'
                station_groups = df.groupby(station_col)

                for station_name, group in station_groups:
                    station_text = self._create_station_sessions_text(station_name, group)
                    station_doc = Document(
                        page_content=station_text,
                        metadata={
                            'source_type': 'illigo_sessions',
                            'data_type': 'station_sessions',
                            'station_id': str(station_name),
                            'session_count': len(group),
                            'file_name': csv_path.name,
                            'agent': 'illigo_operator'
                        }
                    )
                    documents.append(station_doc)

            return documents

        except Exception as e:
            logger.error(f"Error loading sessions CSV: {str(e)}")
            return []

    def _create_sessions_summary(self, df: pd.DataFrame) -> str:
        """Create a summary text from sessions dataframe."""
        text_parts = [
            "ILLIGO CHARGING SESSIONS SUMMARY",
            f"Total Sessions: {len(df)}"
        ]

        # Add column-specific summaries
        if 'energy_kwh' in df.columns or 'energy' in df.columns:
            energy_col = 'energy_kwh' if 'energy_kwh' in df.columns else 'energy'
            total_energy = df[energy_col].sum()
            avg_energy = df[energy_col].mean()
            text_parts.append(f"Total Energy Delivered: {total_energy:.2f} kWh")
            text_parts.append(f"Average Session Energy: {avg_energy:.2f} kWh")

        if 'duration' in df.columns or 'duration_minutes' in df.columns:
            dur_col = 'duration' if 'duration' in df.columns else 'duration_minutes'
            avg_duration = df[dur_col].mean()
            text_parts.append(f"Average Session Duration: {avg_duration:.1f} minutes")

        if 'station' in df.columns or 'station_id' in df.columns:
            station_col = 'station' if 'station' in df.columns else 'station_id'
            station_count = df[station_col].nunique()
            text_parts.append(f"Unique Stations: {station_count}")

        return ". ".join(text_parts) + "."

    def _create_station_sessions_text(self, station_name: str, group: pd.DataFrame) -> str:
        """Create text summary for a single station's sessions."""
        text_parts = [
            f"Station: {station_name}",
            f"Total Sessions: {len(group)}"
        ]

        if 'energy_kwh' in group.columns or 'energy' in group.columns:
            energy_col = 'energy_kwh' if 'energy_kwh' in group.columns else 'energy'
            total_energy = group[energy_col].sum()
            avg_energy = group[energy_col].mean()
            text_parts.append(f"Total Energy: {total_energy:.2f} kWh")
            text_parts.append(f"Average Session Energy: {avg_energy:.2f} kWh")

        return ". ".join(text_parts) + "."

    def load_station_metadata(self) -> List[Document]:
        """
        Load station metadata from CSV.

        Returns:
            List of Document objects with station metadata
        """
        csv_path = self.data_dir / "stations_metadata.csv"

        if not csv_path.exists():
            logger.warning(f"Station metadata CSV not found: {csv_path}")
            return []

        logger.info(f"Loading station metadata: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8', on_bad_lines='warn')
            logger.info(f"Loaded {len(df)} station records")

            documents = []

            for idx, row in df.iterrows():
                station_text = self._station_metadata_to_text(row)
                station_doc = Document(
                    page_content=station_text,
                    metadata={
                        'source_type': 'illigo_metadata',
                        'data_type': 'station_info',
                        'station_id': str(row.get('station_id', row.get('id', f'STATION_{idx}'))),
                        'file_name': csv_path.name,
                        'agent': 'illigo_operator'
                    }
                )
                documents.append(station_doc)

            return documents

        except Exception as e:
            logger.error(f"Error loading station metadata: {str(e)}")
            return []

    def _station_metadata_to_text(self, row: pd.Series) -> str:
        """Convert station metadata row to natural language."""
        text_parts = []

        for col in row.index:
            value = row[col]
            if pd.notna(value):
                # Convert column name to readable format
                col_name = col.replace('_', ' ').title()
                text_parts.append(f"{col_name}: {value}")

        return ". ".join(text_parts) + "."

    def load_connector_data(self) -> List[Document]:
        """
        Load connector data from CSV.

        Returns:
            List of Document objects with connector information
        """
        csv_path = self.data_dir / "station_connectors.csv"

        if not csv_path.exists():
            logger.warning(f"Connector CSV not found: {csv_path}")
            return []

        logger.info(f"Loading connector data: {csv_path}")

        try:
            df = pd.read_csv(csv_path, encoding='utf-8', on_bad_lines='warn')
            logger.info(f"Loaded {len(df)} connector records")

            # Create one document per station (grouped connectors)
            documents = []

            # Check for various station column names (site, station_id, station)
            station_col = None
            for col_name in ['site', 'station_id', 'station']:
                if col_name in df.columns:
                    station_col = col_name
                    break

            if station_col:
                station_groups = df.groupby(station_col)

                for station_name, group in station_groups:
                    connector_text = self._create_connectors_text(station_name, group)
                    connector_doc = Document(
                        page_content=connector_text,
                        metadata={
                            'source_type': 'illigo_connectors',
                            'data_type': 'connector_info',
                            'station_id': str(station_name),
                            'connector_count': len(group),
                            'file_name': csv_path.name,
                            'agent': 'illigo_operator'
                        }
                    )
                    documents.append(connector_doc)

            return documents

        except Exception as e:
            logger.error(f"Error loading connector data: {str(e)}")
            return []

    def _create_connectors_text(self, station_name: str, group: pd.DataFrame) -> str:
        """Create text summary for station connectors."""
        text_parts = [
            f"Station: {station_name}",
            f"Number of Connectors: {len(group)}"
        ]

        for idx, row in group.iterrows():
            connector_info = []
            for col in group.columns:
                if col not in ['station_id', 'station'] and pd.notna(row[col]):
                    connector_info.append(f"{col}: {row[col]}")
            if connector_info:
                text_parts.append(f"Connector: {', '.join(connector_info)}")

        return ". ".join(text_parts) + "."

    def generate_mock_fault_logs(self) -> List[Dict[str, Any]]:
        """
        Generate mock OCPP fault event logs for thesis scenarios.

        Returns:
            List of fault event dictionaries
        """
        logger.info("Generating mock fault logs")

        fault_events = [
            # Primary fault event - Ground Fault at Koumassi
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
            # Status change before fault
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
            # Boot notification
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
            # Over current at ANGRÉ
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
            },
            # Communication failure at Abatta
            {
                "event_id": "EVT_005",
                "station_id": "Petro Ivoire ABATTA",
                "station_code": "ABATTA",
                "timestamp": "2026-01-15T16:30:00",
                "event_type": "FaultNotification",
                "fault_code": "CX010",
                "fault_name": "Communication Failure",
                "severity": "Medium",
                "description": "Communication with backend lost temporarily",
                "connector_id": None,
                "vendor_error_code": "COMM_TIMEOUT",
                "info": "OCPP WebSocket connection timed out after 30s",
                "ocpp_version": "2.0.1",
                "status": "Offline"
            }
        ]

        logger.info(f"Generated {len(fault_events)} mock fault events")
        return fault_events

    def _fault_event_to_text(self, event: Dict[str, Any]) -> str:
        """Convert a fault event dictionary to natural language."""
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

        text_parts.append(f"Status: {event['status']}")

        return ". ".join(text_parts) + "."

    def load(self) -> List[Document]:
        """
        Load all Illigo data: PDFs, CSVs, and mock fault logs.

        Returns:
            List of LangChain Documents
        """
        logger.info(f"Loading Illigo charging station data from {self.data_dir}")

        if not self.data_dir.exists():
            logger.warning(f"Data directory not found: {self.data_dir}. Creating it.")
            self.data_dir.mkdir(parents=True, exist_ok=True)
            return []

        documents = []

        # Load PDF statistics
        pdf_files = list(self.data_dir.glob("*.pdf"))
        for pdf_file in pdf_files:
            try:
                pdf_text = self.extract_pdf_text(pdf_file)
                if pdf_text:
                    pdf_doc = Document(
                        page_content=f"ILLIGO CHARGING STATION STATISTICS\n\n{pdf_text}",
                        metadata={
                            'source_type': 'illigo_statistics',
                            'data_type': 'baseline_performance',
                            'file_name': pdf_file.name,
                            'content_type': 'pdf_statistics',
                            'agent': 'illigo_operator'
                        }
                    )
                    documents.append(pdf_doc)
                    logger.info(f"Added PDF statistics: {pdf_file.name}")
            except Exception as e:
                logger.warning(f"Could not load PDF {pdf_file.name}: {str(e)}")

        # Load CSV data
        session_docs = self.load_sessions_csv()
        documents.extend(session_docs)
        logger.info(f"Added {len(session_docs)} session documents")

        metadata_docs = self.load_station_metadata()
        documents.extend(metadata_docs)
        logger.info(f"Added {len(metadata_docs)} metadata documents")

        connector_docs = self.load_connector_data()
        documents.extend(connector_docs)
        logger.info(f"Added {len(connector_docs)} connector documents")

        # Generate mock fault logs
        fault_events = self.generate_mock_fault_logs()
        for event in fault_events:
            event_text = self._fault_event_to_text(event)
            fault_doc = Document(
                page_content=event_text,
                metadata={
                    'source_type': 'illigo_fault_logs',
                    'data_type': 'fault_event',
                    'event_id': event['event_id'],
                    'station_id': event['station_code'],
                    'timestamp': event['timestamp'],
                    'fault_code': event.get('fault_code'),
                    'severity': event['severity'],
                    'event_type': event['event_type'],
                    'content_type': 'ocpp_event',
                    'agent': 'illigo_operator',
                    'raw_event': json.dumps(event)
                }
            )
            documents.append(fault_doc)

        logger.info(f"Total documents created: {len(documents)}")
        return documents


def main():
    """Test the Illigo loader."""
    logger.info("=" * 60)
    logger.info("Testing Illigo Operator Data Loader")
    logger.info("=" * 60)

    try:
        loader = IlligoLoader()
        documents = loader.load()

        logger.info(f"\nSuccessfully loaded {len(documents)} documents")

        if documents:
            # Group by data type
            by_type = {}
            for doc in documents:
                dt = doc.metadata.get('data_type', 'unknown')
                by_type[dt] = by_type.get(dt, 0) + 1

            logger.info("\nDocuments by type:")
            for dt, count in by_type.items():
                logger.info(f"  {dt}: {count}")

            # Display sample document
            logger.info("\n" + "=" * 60)
            logger.info("SAMPLE DOCUMENT:")
            logger.info("=" * 60)
            print(f"\nContent:\n{documents[0].page_content[:500]}...\n")
            print(f"Metadata:\n{documents[0].metadata}\n")

        logger.info("=" * 60)
        logger.info("Loader test completed!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
