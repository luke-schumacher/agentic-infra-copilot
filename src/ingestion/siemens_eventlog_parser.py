"""
Siemens Event Log Parser - MRI Telemetry Data Ingestion

Parses Siemens MRI system event logs from Windows Event Viewer exports.
Extracts protocol start/stop events, thermal warnings, and fault patterns
for the Telemetry Agent.

Log Format (tab-delimited):
    Level | Date | Time | Source | EventID | Description

Key Event Sources:
    - syngo.MR.HostInfra.Telemetry: Shutdown steps (50410, 50411, 50419)
    - syngo_Application: LCMService process lifecycle
    - syngo.MR.HostInfra.FilesystemCleanup: Storage management

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from langchain_core.documents import Document
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SiemensEventLog(BaseModel):
    """Parsed event from Siemens MRI event log."""
    level: str = Field(description="Event level: W=Warning, I=Info, E=Error")
    date: str = Field(description="Event date YYYY-MM-DD")
    time: str = Field(description="Event time HH:MM:SS")
    source: str = Field(description="Event source (service/component name)")
    event_id: int = Field(description="Numeric event identifier")
    description: str = Field(description="Full event description")
    severity: str = Field(description="Normalized severity: info, warning, error")
    timestamp: datetime = Field(description="Combined datetime")

    @property
    def is_mri_specific(self) -> bool:
        """Check if event is MRI-specific (syngo prefix)."""
        return self.source.startswith('syngo')

    @property
    def is_telemetry_event(self) -> bool:
        """Check if event is from telemetry service."""
        return 'Telemetry' in self.source

    @property
    def is_thermal_event(self) -> bool:
        """Check if event relates to thermal management."""
        thermal_keywords = ['thermal', 'temperature', 'cooling', 'overheat']
        return any(kw in self.description.lower() for kw in thermal_keywords)


class ProtocolEvent(BaseModel):
    """Extracted protocol execution event."""
    event_type: str = Field(description="start, step, or done")
    timestamp: datetime
    step_name: Optional[str] = None
    shutdown_type: Optional[str] = None


class IdleTimePeriod(BaseModel):
    """Calculated idle time period between sessions."""
    start_time: datetime
    end_time: datetime
    duration_minutes: float
    preceding_event: str
    following_event: str


class SiemensEventLogParser:
    """
    Parser for Siemens MRI event logs.

    Extracts telemetry data for fault diagnosis including:
    - Protocol start/stop events for session tracking
    - Thermal and fault patterns
    - Idle time calculations
    """

    # Event level mapping
    LEVEL_MAP = {
        'I': 'info',
        'W': 'warning',
        'E': 'error'
    }

    # Key event IDs for shutdown telemetry
    SHUTDOWN_START_ID = 50410
    SHUTDOWN_STEP_ID = 50411
    SHUTDOWN_DONE_ID = 50419

    def __init__(self, log_dir: str = "data/raw/siemens/eventlog_txt"):
        """
        Initialize parser.

        Args:
            log_dir: Directory containing event log files
        """
        self.log_dir = Path(log_dir)

    def parse_line(self, line: str) -> Optional[SiemensEventLog]:
        """
        Parse a single line from the event log.

        Args:
            line: Tab-delimited log line

        Returns:
            SiemensEventLog or None if parse fails
        """
        parts = line.strip().split('\t')
        if len(parts) < 6:
            return None

        try:
            level = parts[0]
            date = parts[1]
            time = parts[2]
            source = parts[3]
            event_id = int(parts[4]) if parts[4].isdigit() else 0
            description = '\t'.join(parts[5:])  # Description may contain tabs

            # Parse timestamp
            timestamp = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M:%S")

            return SiemensEventLog(
                level=level,
                date=date,
                time=time,
                source=source,
                event_id=event_id,
                description=description,
                severity=self.LEVEL_MAP.get(level, 'info'),
                timestamp=timestamp
            )
        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse line: {line[:100]}... Error: {e}")
            return None

    def parse_file(self, path: Path) -> List[SiemensEventLog]:
        """
        Parse all events from a log file.

        Args:
            path: Path to log file

        Returns:
            List of parsed events
        """
        logger.info(f"Parsing event log: {path}")
        events = []

        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue
                event = self.parse_line(line)
                if event:
                    events.append(event)

                if line_num % 50000 == 0:
                    logger.info(f"Processed {line_num} lines...")

        logger.info(f"Parsed {len(events)} events from {path.name}")
        return events

    def extract_mri_specific_events(
        self,
        events: List[SiemensEventLog]
    ) -> List[SiemensEventLog]:
        """
        Filter to MRI-specific events (syngo prefix).

        Args:
            events: List of all events

        Returns:
            Filtered list of MRI events
        """
        mri_events = [e for e in events if e.is_mri_specific]
        logger.info(f"Filtered to {len(mri_events)} MRI-specific events")
        return mri_events

    def extract_protocol_events(
        self,
        events: List[SiemensEventLog]
    ) -> List[ProtocolEvent]:
        """
        Extract protocol start/stop/step events from telemetry.

        These events track shutdown sequences and can be correlated
        with session failures.

        Args:
            events: List of all events

        Returns:
            List of protocol events
        """
        protocol_events = []

        # Pattern for shutdown step extraction
        step_pattern = re.compile(r'step=(\w+)')
        type_pattern = re.compile(r'ShutdownRequestType=(\w+)')

        for event in events:
            if not event.is_telemetry_event:
                continue

            if event.event_id == self.SHUTDOWN_START_ID:
                # Extract shutdown type
                match = type_pattern.search(event.description)
                shutdown_type = match.group(1) if match else None
                protocol_events.append(ProtocolEvent(
                    event_type='start',
                    timestamp=event.timestamp,
                    shutdown_type=shutdown_type
                ))

            elif event.event_id == self.SHUTDOWN_STEP_ID:
                # Extract step name
                match = step_pattern.search(event.description)
                step_name = match.group(1) if match else None
                protocol_events.append(ProtocolEvent(
                    event_type='step',
                    timestamp=event.timestamp,
                    step_name=step_name
                ))

            elif event.event_id == self.SHUTDOWN_DONE_ID:
                protocol_events.append(ProtocolEvent(
                    event_type='done',
                    timestamp=event.timestamp
                ))

        logger.info(f"Extracted {len(protocol_events)} protocol events")
        return protocol_events

    def calculate_idle_times(
        self,
        events: List[SiemensEventLog],
        min_idle_minutes: float = 5.0
    ) -> List[IdleTimePeriod]:
        """
        Calculate idle time periods between events.

        Idle time analysis helps identify:
        - Unexpected gaps in operation
        - Thermal cooldown periods
        - Session scheduling patterns

        Args:
            events: List of events sorted by time
            min_idle_minutes: Minimum gap to consider as idle

        Returns:
            List of idle time periods
        """
        if len(events) < 2:
            return []

        # Sort events by timestamp (newest first in log, so reverse)
        sorted_events = sorted(events, key=lambda e: e.timestamp)

        idle_periods = []

        for i in range(1, len(sorted_events)):
            prev_event = sorted_events[i-1]
            curr_event = sorted_events[i]

            gap = (curr_event.timestamp - prev_event.timestamp).total_seconds() / 60.0

            if gap >= min_idle_minutes:
                idle_periods.append(IdleTimePeriod(
                    start_time=prev_event.timestamp,
                    end_time=curr_event.timestamp,
                    duration_minutes=gap,
                    preceding_event=f"{prev_event.source}: {prev_event.description[:50]}",
                    following_event=f"{curr_event.source}: {curr_event.description[:50]}"
                ))

        logger.info(f"Found {len(idle_periods)} idle periods >= {min_idle_minutes} minutes")
        return idle_periods

    def extract_fault_patterns(
        self,
        events: List[SiemensEventLog],
        window_minutes: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Detect recurring fault patterns (e.g., 90-minute thermal cycles).

        This is critical for the "Cascading Thermal Fault" emergence test case.

        Args:
            events: List of events
            window_minutes: Time window for pattern detection

        Returns:
            List of detected patterns with timestamps
        """
        # Filter to warnings and errors
        fault_events = [e for e in events if e.severity in ('warning', 'error')]

        if len(fault_events) < 2:
            return []

        patterns = []
        window_delta = timedelta(minutes=window_minutes)

        # Group faults by description similarity
        fault_groups: Dict[str, List[datetime]] = {}

        for event in fault_events:
            # Create a key from source and first 50 chars of description
            key = f"{event.source}:{event.description[:50]}"
            if key not in fault_groups:
                fault_groups[key] = []
            fault_groups[key].append(event.timestamp)

        # Detect recurring patterns
        for key, timestamps in fault_groups.items():
            if len(timestamps) < 2:
                continue

            sorted_times = sorted(timestamps)
            intervals = []

            for i in range(1, len(sorted_times)):
                interval = (sorted_times[i] - sorted_times[i-1]).total_seconds() / 60.0
                intervals.append(interval)

            if intervals:
                avg_interval = sum(intervals) / len(intervals)

                # Check if pattern is close to window_minutes
                if abs(avg_interval - window_minutes) < window_minutes * 0.2:  # 20% tolerance
                    patterns.append({
                        'fault_signature': key,
                        'occurrences': len(timestamps),
                        'avg_interval_minutes': avg_interval,
                        'timestamps': [t.isoformat() for t in sorted_times],
                        'suspected_pattern': f"~{window_minutes} minute cycle detected"
                    })

        logger.info(f"Detected {len(patterns)} recurring fault patterns")
        return patterns

    def to_documents(
        self,
        events: List[SiemensEventLog],
        include_all: bool = False
    ) -> List[Document]:
        """
        Convert events to LangChain Documents for vector storage.

        Args:
            events: List of events to convert
            include_all: If True, include all events; else only MRI-specific

        Returns:
            List of Document objects
        """
        documents = []

        # Filter events
        target_events = events if include_all else self.extract_mri_specific_events(events)

        # Group events by hour for chunking
        hourly_groups: Dict[str, List[SiemensEventLog]] = {}

        for event in target_events:
            hour_key = event.timestamp.strftime("%Y-%m-%d %H:00")
            if hour_key not in hourly_groups:
                hourly_groups[hour_key] = []
            hourly_groups[hour_key].append(event)

        # Create documents for each hour
        for hour_key, hour_events in hourly_groups.items():
            # Build summary text
            text_parts = [f"MRI Event Log Summary for {hour_key}"]
            text_parts.append(f"Total events: {len(hour_events)}")

            # Count by severity
            severity_counts = {'info': 0, 'warning': 0, 'error': 0}
            for e in hour_events:
                severity_counts[e.severity] += 1

            text_parts.append(
                f"Severity breakdown: {severity_counts['error']} errors, "
                f"{severity_counts['warning']} warnings, {severity_counts['info']} info"
            )

            # List significant events (warnings and errors)
            significant = [e for e in hour_events if e.severity != 'info']
            if significant:
                text_parts.append("\nSignificant events:")
                for e in significant[:10]:  # Limit to 10 per chunk
                    text_parts.append(
                        f"- [{e.time}] {e.severity.upper()}: {e.source} - {e.description[:100]}"
                    )

            doc = Document(
                page_content='\n'.join(text_parts),
                metadata={
                    'source': 'siemens_mri_eventlog',
                    'hour': hour_key,
                    'event_count': len(hour_events),
                    'error_count': severity_counts['error'],
                    'warning_count': severity_counts['warning'],
                    'data_type': 'telemetry'
                }
            )
            documents.append(doc)

        logger.info(f"Created {len(documents)} Document chunks from events")
        return documents

    def load(self) -> List[Document]:
        """
        Load all event logs from directory and convert to Documents.

        Returns:
            List of Document objects
        """
        all_events = []

        if not self.log_dir.exists():
            logger.warning(f"Event log directory not found: {self.log_dir}")
            return []

        # Find all .txt files in directory
        log_files = list(self.log_dir.glob("*.txt"))

        if not log_files:
            logger.warning(f"No .txt files found in {self.log_dir}")
            return []

        for log_file in log_files:
            events = self.parse_file(log_file)
            all_events.extend(events)

        return self.to_documents(all_events)


def main():
    """Test the Siemens event log parser."""
    logger.info("=" * 60)
    logger.info("Testing Siemens Event Log Parser")
    logger.info("=" * 60)

    parser = SiemensEventLogParser()

    # Test with actual file if exists
    test_file = Path("data/raw/siemens/eventlog_txt/MR176571_EvtLog_20251210.txt")

    if test_file.exists():
        events = parser.parse_file(test_file)

        logger.info(f"\nParsed {len(events)} total events")

        # Extract MRI-specific events
        mri_events = parser.extract_mri_specific_events(events)
        logger.info(f"MRI-specific events: {len(mri_events)}")

        # Extract protocol events
        protocol_events = parser.extract_protocol_events(events)
        logger.info(f"Protocol events: {len(protocol_events)}")

        # Calculate idle times
        idle_periods = parser.calculate_idle_times(mri_events, min_idle_minutes=10)
        logger.info(f"Idle periods (>=10 min): {len(idle_periods)}")

        # Detect fault patterns
        fault_patterns = parser.extract_fault_patterns(events, window_minutes=90)
        logger.info(f"Fault patterns detected: {len(fault_patterns)}")

        # Convert to documents
        docs = parser.to_documents(events)
        logger.info(f"Created {len(docs)} document chunks")

        if docs:
            logger.info("\nExample document:")
            print(docs[0].page_content[:500])
            print(f"\nMetadata: {docs[0].metadata}")
    else:
        logger.info(f"Test file not found: {test_file}")
        logger.info("Creating parser for later use...")

    logger.info("\n" + "=" * 60)
    logger.info("Parser test complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
