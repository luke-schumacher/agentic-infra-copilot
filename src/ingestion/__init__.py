"""
Ingestion Module - Custom parsers for PDF, CSV, and JSON data sources.

Includes:
- siemens_loader: CSV questionnaire data
- siemens_eventlog_parser: MRI event log telemetry
- radlex_loader: RSNA RadReport templates with RadLex ontology
- telekom_loader: OCPP/SLA documentation
- illigo_loader: EV charging station data
"""

from src.ingestion.siemens_eventlog_parser import (
    SiemensEventLog,
    SiemensEventLogParser,
    ProtocolEvent,
    IdleTimePeriod
)
from src.ingestion.radlex_loader import (
    RadLexTerm,
    ExaminationTemplate,
    RadLexLoader
)

__all__ = [
    'SiemensEventLog',
    'SiemensEventLogParser',
    'ProtocolEvent',
    'IdleTimePeriod',
    'RadLexTerm',
    'ExaminationTemplate',
    'RadLexLoader'
]
