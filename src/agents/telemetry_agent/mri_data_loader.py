"""
MRI Telemetry Data Loader - Siemens Event Log Processing

Processes preprocessed MRI telemetry data for the Telemetry Agent:
1. Loads structured event logs (mri_events.csv)
2. Loads detected fault patterns
3. Loads failure mode definitions
4. Enables temporal pattern analysis

Environment Variables:
- TELEMETRY_DATA_DIR: Path to processed telemetry data (default: data/processed/telemetry)
- RAW_LOGS_DIR: Path to raw event logs (default: data/raw/siemens/eventlog_txt)

Author: Thesis Project - Healthcare MAS
"""

import os
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from langchain_core.documents import Document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default paths (can be overridden via environment variables)
DEFAULT_PROCESSED_DIR = "data/processed/telemetry"
DEFAULT_RAW_LOGS_DIR = "data/raw/siemens/eventlog_txt"


class MRITelemetryLoader:
    """Loads MRI telemetry data for the Telemetry Agent."""

    def __init__(
        self,
        data_dir: Optional[str] = None,
        raw_dir: Optional[str] = None
    ):
        """
        Initialize the MRI telemetry loader.

        Args:
            data_dir: Directory containing processed telemetry CSVs (env: TELEMETRY_DATA_DIR)
            raw_dir: Directory containing raw event logs (env: RAW_LOGS_DIR)
        """
        self.data_dir = Path(
            data_dir or os.getenv("TELEMETRY_DATA_DIR", DEFAULT_PROCESSED_DIR)
        )
        self.raw_dir = Path(
            raw_dir or os.getenv("RAW_LOGS_DIR", DEFAULT_RAW_LOGS_DIR)
        )

        logger.info(f"MRITelemetryLoader initialized with data_dir={self.data_dir}")

    def load_events(self, max_events: int = 50000) -> List[Document]:
        """
        Load MRI events from preprocessed CSV.

        Args:
            max_events: Maximum events to load (for memory management)

        Returns:
            List of Document objects with event data
        """
        events_csv = self.data_dir / "mri_events.csv"

        if not events_csv.exists():
            logger.warning(f"Events CSV not found: {events_csv}")
            return []

        logger.info(f"Loading MRI events from: {events_csv}")

        try:
            # Load with chunking for large files
            df = pd.read_csv(events_csv, nrows=max_events)
            logger.info(f"Loaded {len(df)} events")

            documents = []

            # Create hourly summary documents (more useful for RAG)
            if 'timestamp' in df.columns:
                df['hour'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:00')
                hourly_groups = df.groupby('hour')

                for hour, group in hourly_groups:
                    doc = self._create_hourly_summary(hour, group)
                    documents.append(doc)
            else:
                # Fallback: chunk by rows
                chunk_size = 100
                for i in range(0, len(df), chunk_size):
                    chunk = df.iloc[i:i+chunk_size]
                    doc = self._create_event_chunk(i, chunk)
                    documents.append(doc)

            logger.info(f"Created {len(documents)} event documents")
            return documents

        except Exception as e:
            logger.error(f"Error loading events: {e}")
            return []

    def _create_hourly_summary(self, hour: str, group: pd.DataFrame) -> Document:
        """Create a summary document for one hour of events."""
        # Count by severity
        severity_counts = group['severity'].value_counts().to_dict() if 'severity' in group.columns else {}

        # Count MRI-specific events
        mri_count = group['is_mri_specific'].sum() if 'is_mri_specific' in group.columns else 0

        # Count thermal events
        thermal_count = group['is_thermal'].sum() if 'is_thermal' in group.columns else 0

        # Get unique sources
        sources = group['source'].unique().tolist()[:10] if 'source' in group.columns else []

        # Build text
        text_parts = [
            f"MRI SYSTEM EVENTS: {hour}",
            f"Total Events: {len(group)}",
            f"Errors: {severity_counts.get('error', 0)}",
            f"Warnings: {severity_counts.get('warning', 0)}",
            f"Info: {severity_counts.get('info', 0)}",
            f"MRI-Specific Events: {mri_count}",
            f"Thermal Events: {thermal_count}",
            f"Sources: {', '.join(sources)}"
        ]

        # Add significant events (errors and warnings)
        significant = group[group['severity'].isin(['error', 'warning'])] if 'severity' in group.columns else pd.DataFrame()
        if len(significant) > 0:
            text_parts.append("\nSignificant Events:")
            for _, event in significant.head(10).iterrows():
                time_str = event.get('time', 'unknown')
                source = event.get('source', 'unknown')
                desc = str(event.get('description', ''))[:150]
                text_parts.append(f"  [{time_str}] {source}: {desc}")

        return Document(
            page_content='\n'.join(text_parts),
            metadata={
                'source_type': 'mri_events',
                'data_type': 'hourly_summary',
                'hour': hour,
                'event_count': len(group),
                'error_count': severity_counts.get('error', 0),
                'warning_count': severity_counts.get('warning', 0),
                'mri_specific_count': int(mri_count),
                'thermal_count': int(thermal_count),
                'agent': 'telemetry_agent'
            }
        )

    def _create_event_chunk(self, start_idx: int, chunk: pd.DataFrame) -> Document:
        """Create a document from a chunk of events."""
        text_parts = [f"MRI EVENTS (records {start_idx} to {start_idx + len(chunk)})"]

        for _, row in chunk.iterrows():
            line = f"[{row.get('timestamp', '')}] {row.get('severity', '').upper()}: {row.get('source', '')} - {str(row.get('description', ''))[:100]}"
            text_parts.append(line)

        return Document(
            page_content='\n'.join(text_parts),
            metadata={
                'source_type': 'mri_events',
                'data_type': 'event_chunk',
                'start_index': start_idx,
                'event_count': len(chunk),
                'agent': 'telemetry_agent'
            }
        )

    def load_detected_patterns(self) -> List[Document]:
        """
        Load detected fault patterns (thermal cycles, recurring errors).

        Returns:
            List of Document objects with pattern data
        """
        patterns_csv = self.data_dir / "detected_patterns.csv"

        if not patterns_csv.exists():
            logger.warning(f"Patterns CSV not found: {patterns_csv}")
            return []

        logger.info(f"Loading detected patterns from: {patterns_csv}")

        try:
            df = pd.read_csv(patterns_csv)
            logger.info(f"Loaded {len(df)} pattern events")

            documents = []

            # Group patterns by type
            if 'is_thermal' in df.columns:
                thermal_patterns = df[df['is_thermal'] == True]
                if len(thermal_patterns) > 0:
                    doc = self._create_pattern_summary("Thermal Patterns", thermal_patterns)
                    documents.append(doc)

            if 'is_error' in df.columns:
                error_patterns = df[df['is_error'] == True]
                if len(error_patterns) > 0:
                    doc = self._create_pattern_summary("Error Patterns", error_patterns)
                    documents.append(doc)

            # Create overall pattern summary
            summary_doc = Document(
                page_content=self._create_pattern_analysis(df),
                metadata={
                    'source_type': 'mri_patterns',
                    'data_type': 'pattern_analysis',
                    'pattern_count': len(df),
                    'agent': 'telemetry_agent'
                }
            )
            documents.append(summary_doc)

            logger.info(f"Created {len(documents)} pattern documents")
            return documents

        except Exception as e:
            logger.error(f"Error loading patterns: {e}")
            return []

    def _create_pattern_summary(self, pattern_type: str, df: pd.DataFrame) -> Document:
        """Create a summary document for a pattern type."""
        text_parts = [
            f"DETECTED PATTERN: {pattern_type}",
            f"Occurrences: {len(df)}"
        ]

        # Analyze temporal distribution
        if 'timestamp' in df.columns:
            timestamps = pd.to_datetime(df['timestamp'])
            if len(timestamps) > 1:
                # Calculate intervals
                timestamps_sorted = timestamps.sort_values()
                intervals = timestamps_sorted.diff().dropna()
                if len(intervals) > 0:
                    avg_interval = intervals.mean()
                    text_parts.append(f"Average Interval: {avg_interval}")

        # Add sample events
        text_parts.append("\nSample Events:")
        for _, row in df.head(5).iterrows():
            text_parts.append(f"  [{row.get('timestamp', '')}] {row.get('source', '')}: {str(row.get('description', ''))[:100]}")

        return Document(
            page_content='\n'.join(text_parts),
            metadata={
                'source_type': 'mri_patterns',
                'data_type': pattern_type.lower().replace(' ', '_'),
                'occurrence_count': len(df),
                'agent': 'telemetry_agent'
            }
        )

    def _create_pattern_analysis(self, df: pd.DataFrame) -> str:
        """Create comprehensive pattern analysis text."""
        text_parts = [
            "MRI SYSTEM PATTERN ANALYSIS",
            f"Total Pattern Events: {len(df)}",
            ""
        ]

        # Severity breakdown
        if 'severity' in df.columns:
            severity_counts = df['severity'].value_counts()
            text_parts.append("Severity Distribution:")
            for sev, count in severity_counts.items():
                text_parts.append(f"  {sev}: {count}")

        # Source breakdown
        if 'source' in df.columns:
            source_counts = df['source'].value_counts().head(10)
            text_parts.append("\nTop Sources:")
            for source, count in source_counts.items():
                text_parts.append(f"  {source}: {count}")

        # Thermal analysis
        if 'is_thermal' in df.columns:
            thermal_count = df['is_thermal'].sum()
            text_parts.append(f"\nThermal-Related Events: {thermal_count}")
            if thermal_count > 0:
                text_parts.append("  Note: Thermal events may indicate sensor or cooling issues")

        return '\n'.join(text_parts)

    def load_failure_modes(self) -> List[Document]:
        """
        Load failure mode definitions.

        Returns:
            List of Document objects with failure mode data
        """
        failure_csv = self.data_dir / "failure_modes.csv"

        if not failure_csv.exists():
            logger.warning(f"Failure modes CSV not found: {failure_csv}")
            return []

        logger.info(f"Loading failure modes from: {failure_csv}")

        try:
            df = pd.read_csv(failure_csv)
            logger.info(f"Loaded {len(df)} failure modes")

            documents = []

            # Create document for each failure mode
            for _, row in df.iterrows():
                doc = self._create_failure_mode_doc(row)
                documents.append(doc)

            # Create summary document
            summary_doc = Document(
                page_content=self._create_failure_mode_summary(df),
                metadata={
                    'source_type': 'failure_modes',
                    'data_type': 'failure_mode_index',
                    'mode_count': len(df),
                    'agent': 'telemetry_agent'
                }
            )
            documents.append(summary_doc)

            logger.info(f"Created {len(documents)} failure mode documents")
            return documents

        except Exception as e:
            logger.error(f"Error loading failure modes: {e}")
            return []

    def _create_failure_mode_doc(self, row: pd.Series) -> Document:
        """Create a document for a single failure mode."""
        text_parts = [
            f"FAILURE MODE: {row.get('failure_mode', 'Unknown')}",
            f"ID: {row.get('failure_id', 'N/A')}",
            f"Component: {row.get('component', 'N/A')}",
            f"Symptom: {row.get('symptom', 'N/A')}",
            f"Root Cause: {row.get('root_cause', 'N/A')}",
            f"Detection Method: {row.get('detection_method', 'N/A')}",
            f"Severity: {row.get('severity', 'N/A')}",
            f"MTTR: {row.get('mttr_hours', 'N/A')} hours",
            f"Repair Action: {row.get('repair_action', 'N/A')}",
            f"Spare Parts: {row.get('spare_parts_required', 'N/A')}",
            f"Preventive Maintenance: {row.get('preventive_maintenance', 'N/A')}"
        ]

        return Document(
            page_content='\n'.join(text_parts),
            metadata={
                'source_type': 'failure_modes',
                'data_type': 'failure_mode',
                'failure_id': row.get('failure_id', ''),
                'failure_mode': row.get('failure_mode', ''),
                'component': row.get('component', ''),
                'severity': row.get('severity', ''),
                'agent': 'telemetry_agent'
            }
        )

    def _create_failure_mode_summary(self, df: pd.DataFrame) -> str:
        """Create summary of all failure modes."""
        text_parts = [
            "MRI SYSTEM FAILURE MODES INDEX",
            f"Total Documented Modes: {len(df)}",
            ""
        ]

        # Group by severity
        if 'severity' in df.columns:
            severity_groups = df.groupby('severity')
            text_parts.append("Failure Modes by Severity:")
            for sev, group in severity_groups:
                modes = ', '.join(group['failure_mode'].head(5).tolist())
                text_parts.append(f"  {sev}: {modes}")

        # Group by component
        if 'component' in df.columns:
            component_counts = df['component'].value_counts().head(10)
            text_parts.append("\nFailure Modes by Component:")
            for comp, count in component_counts.items():
                text_parts.append(f"  {comp}: {count} modes")

        return '\n'.join(text_parts)

    def load_event_summary(self) -> Optional[Document]:
        """
        Load overall event summary statistics.

        Returns:
            Document with summary statistics
        """
        summary_csv = self.data_dir / "event_summary.csv"

        if not summary_csv.exists():
            logger.warning(f"Event summary not found: {summary_csv}")
            return None

        try:
            df = pd.read_csv(summary_csv)

            # Convert to dict
            summary = dict(zip(df['metric'], df['value']))

            text_parts = [
                "MRI SYSTEM EVENT LOG SUMMARY",
                f"Total Events Analyzed: {summary.get('total_events', 'N/A')}",
                f"Info Events: {summary.get('info_count', 'N/A')}",
                f"Warning Events: {summary.get('warning_count', 'N/A')}",
                f"Error Events: {summary.get('error_count', 'N/A')}",
                f"Unique Event Sources: {summary.get('unique_sources', 'N/A')}",
                f"MRI-Specific Events: {summary.get('mri_specific_events', 'N/A')}",
                f"Thermal-Related Events: {summary.get('thermal_events', 'N/A')}",
                "",
                "Analysis Notes:",
                "- High thermal event count may indicate sensor calibration issues",
                "- Check for 90-minute patterns in thermal shutdowns",
                "- MRI-specific events (syngo.*) are most relevant for diagnosis"
            ]

            return Document(
                page_content='\n'.join(text_parts),
                metadata={
                    'source_type': 'event_summary',
                    'data_type': 'statistics',
                    'total_events': summary.get('total_events', 0),
                    'error_count': summary.get('error_count', 0),
                    'warning_count': summary.get('warning_count', 0),
                    'thermal_events': summary.get('thermal_events', 0),
                    'agent': 'telemetry_agent'
                }
            )

        except Exception as e:
            logger.error(f"Error loading summary: {e}")
            return None

    def load(self) -> List[Document]:
        """
        Load all MRI telemetry data.

        Returns:
            List of LangChain Documents
        """
        logger.info(f"Loading MRI telemetry data from {self.data_dir}")

        if not self.data_dir.exists():
            logger.warning(f"Data directory not found: {self.data_dir}")
            return []

        documents = []

        # Load event summary first (most important context)
        summary_doc = self.load_event_summary()
        if summary_doc:
            documents.append(summary_doc)

        # Load failure modes (critical for diagnosis)
        failure_docs = self.load_failure_modes()
        documents.extend(failure_docs)

        # Load detected patterns
        pattern_docs = self.load_detected_patterns()
        documents.extend(pattern_docs)

        # Load event details (sampled)
        event_docs = self.load_events(max_events=50000)
        documents.extend(event_docs)

        logger.info(f"Total documents loaded: {len(documents)}")
        return documents


def main():
    """Test the MRI telemetry loader."""
    logger.info("=" * 60)
    logger.info("Testing MRI Telemetry Data Loader")
    logger.info("=" * 60)

    try:
        loader = MRITelemetryLoader()
        documents = loader.load()

        logger.info(f"\nSuccessfully loaded {len(documents)} documents")

        if documents:
            # Group by data type
            by_type = {}
            for doc in documents:
                dt = doc.metadata.get('data_type', 'unknown')
                by_type[dt] = by_type.get(dt, 0) + 1

            logger.info("\nDocuments by type:")
            for dt, count in sorted(by_type.items()):
                logger.info(f"  {dt}: {count}")

            # Show sample document
            logger.info("\n" + "=" * 60)
            logger.info("SAMPLE DOCUMENT:")
            logger.info("=" * 60)
            print(f"\nContent:\n{documents[0].page_content}\n")
            print(f"Metadata: {documents[0].metadata}\n")

        logger.info("=" * 60)
        logger.info("Loader test completed!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
