"""
Illigo Operator Brain - DSPy Signatures for Live Monitor Agent

Defines DSPy signatures for:
- OCPP event log analysis
- Anomaly detection in charging station data
- Real-time fault correlation
- Temporal event pattern recognition

Domain: EV charging station operations and OCPP 2.0.1 event logs
Data: Illigo charging station statistics, fault events, session data

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import dspy
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalyzeFaultEvent(dspy.Signature):
    """
    Analyze a fault event from OCPP logs to determine root cause and impact.

    Given a fault event description and historical context, determine:
    1. Root cause analysis
    2. Impact assessment on charging operations
    3. Recommended corrective actions
    """
    fault_description: str = dspy.InputField(
        desc="Description of the fault event from OCPP logs"
    )
    station_context: str = dspy.InputField(
        desc="Historical performance data and previous events for the station"
    )
    timestamp: str = dspy.InputField(
        desc="Timestamp of the fault event"
    )

    root_cause: str = dspy.OutputField(
        desc="Identified root cause of the fault"
    )
    impact: str = dspy.OutputField(
        desc="Impact on charging operations and service availability"
    )
    severity: str = dspy.OutputField(
        desc="Severity level: 'low', 'medium', 'high', or 'critical'"
    )
    corrective_actions: str = dspy.OutputField(
        desc="Recommended corrective actions to resolve the fault"
    )


class DetectAnomaly(dspy.Signature):
    """
    Detect anomalies in charging station performance data.

    Compares current metrics against baseline performance to identify
    deviations that may indicate emerging issues.
    """
    current_metrics: str = dspy.InputField(
        desc="Current performance metrics (energy consumption, session counts, etc.)"
    )
    baseline_metrics: str = dspy.InputField(
        desc="Historical baseline performance data"
    )
    station_id: str = dspy.InputField(
        desc="Identifier of the charging station"
    )

    is_anomaly: str = dspy.OutputField(
        desc="'yes' if anomaly detected, 'no' otherwise"
    )
    anomaly_type: str = dspy.OutputField(
        desc="Type of anomaly if detected (e.g., 'load_imbalance', 'session_drop', 'energy_spike')"
    )
    deviation_description: str = dspy.OutputField(
        desc="Description of the deviation from baseline"
    )
    risk_level: str = dspy.OutputField(
        desc="Risk level of the anomaly: 'low', 'medium', 'high'"
    )


class CorrelateEvents(dspy.Signature):
    """
    Correlate multiple events to identify patterns and cascading failures.

    Analyzes temporal relationships between events to identify
    cause-effect chains and systemic issues.
    """
    event_sequence: str = dspy.InputField(
        desc="Sequence of events with timestamps"
    )
    time_window: str = dspy.InputField(
        desc="Time window for correlation analysis (e.g., '1 hour', '24 hours')"
    )

    correlation_found: str = dspy.OutputField(
        desc="'yes' if correlated events found, 'no' otherwise"
    )
    pattern_description: str = dspy.OutputField(
        desc="Description of the identified event pattern"
    )
    causal_chain: str = dspy.OutputField(
        desc="Identified cause-effect chain if applicable"
    )
    affected_stations: str = dspy.OutputField(
        desc="List of stations affected by correlated events"
    )


class QueryStationStatus(dspy.Signature):
    """
    Query and synthesize current station status information.

    Used to answer questions about charging station operations,
    session data, and performance metrics.
    """
    query: str = dspy.InputField(
        desc="User's question about station status or operations"
    )
    station_data: str = dspy.InputField(
        desc="Retrieved station data including statistics and event logs"
    )

    answer: str = dspy.OutputField(
        desc="Direct answer to the query based on station data"
    )
    data_summary: str = dspy.OutputField(
        desc="Summary of relevant data points referenced"
    )
    confidence: str = dspy.OutputField(
        desc="Confidence level: 'high', 'medium', or 'low'"
    )


class AnalyzeLoadBalance(dspy.Signature):
    """
    Analyze load balance across charging stations.

    Identifies load imbalances between stations that may indicate
    infrastructure issues or demand planning problems.
    """
    station_loads: str = dspy.InputField(
        desc="Energy consumption data for multiple stations"
    )
    time_period: str = dspy.InputField(
        desc="Time period for analysis"
    )

    imbalance_detected: str = dspy.OutputField(
        desc="'yes' if significant load imbalance detected, 'no' otherwise"
    )
    overloaded_stations: str = dspy.OutputField(
        desc="Stations with above-normal load"
    )
    underutilized_stations: str = dspy.OutputField(
        desc="Stations with below-normal load"
    )
    recommendations: str = dspy.OutputField(
        desc="Recommendations for balancing load"
    )


class IlligoOperatorModule(dspy.Module):
    """
    Main DSPy module for Illigo Operator agent.

    Combines multiple signatures into a cohesive live monitoring expert:
    1. Analyze fault events from OCPP logs
    2. Detect anomalies in performance data
    3. Correlate events across time and stations
    4. Query station status and operations
    5. Analyze load balance
    """

    def __init__(self):
        super().__init__()
        self.analyze_fault = dspy.ChainOfThought(AnalyzeFaultEvent)
        self.detect_anomaly = dspy.ChainOfThought(DetectAnomaly)
        self.correlate_events = dspy.ChainOfThought(CorrelateEvents)
        self.query_status = dspy.ChainOfThought(QueryStationStatus)
        self.analyze_load = dspy.ChainOfThought(AnalyzeLoadBalance)

    def forward(
        self,
        query: str,
        context: str,
        query_type: str = "general",
        station_id: str = "unknown",
        timestamp: str = ""
    ) -> dspy.Prediction:
        """
        Process an incoming query through the Operator's reasoning.

        Args:
            query: User query or event description
            context: Retrieved station data and event logs
            query_type: Type of query - 'fault', 'anomaly', 'correlation', 'status', or 'load'
            station_id: Station identifier if applicable
            timestamp: Timestamp if applicable

        Returns:
            DSPy Prediction with appropriate response based on query type
        """
        logger.info(f"Processing query (type={query_type}): {query[:100]}...")

        if query_type == "fault":
            result = self.analyze_fault(
                fault_description=query,
                station_context=context,
                timestamp=timestamp or "unknown"
            )
            return dspy.Prediction(
                root_cause=result.root_cause,
                impact=result.impact,
                severity=result.severity,
                corrective_actions=result.corrective_actions,
                answer=f"Root cause: {result.root_cause}. Impact: {result.impact}. Actions: {result.corrective_actions}"
            )

        elif query_type == "anomaly":
            result = self.detect_anomaly(
                current_metrics=query,
                baseline_metrics=context,
                station_id=station_id
            )
            return dspy.Prediction(
                is_anomaly=result.is_anomaly,
                anomaly_type=result.anomaly_type,
                deviation_description=result.deviation_description,
                risk_level=result.risk_level,
                answer=f"Anomaly: {result.is_anomaly}. Type: {result.anomaly_type}. {result.deviation_description}"
            )

        elif query_type == "correlation":
            result = self.correlate_events(
                event_sequence=query,
                time_window=timestamp or "24 hours"
            )
            return dspy.Prediction(
                correlation_found=result.correlation_found,
                pattern_description=result.pattern_description,
                causal_chain=result.causal_chain,
                affected_stations=result.affected_stations,
                answer=f"Pattern: {result.pattern_description}. Causal chain: {result.causal_chain}"
            )

        elif query_type == "load":
            result = self.analyze_load(
                station_loads=context,
                time_period=timestamp or "last 24 hours"
            )
            return dspy.Prediction(
                imbalance_detected=result.imbalance_detected,
                overloaded_stations=result.overloaded_stations,
                underutilized_stations=result.underutilized_stations,
                recommendations=result.recommendations,
                answer=f"Load imbalance: {result.imbalance_detected}. {result.recommendations}"
            )

        else:
            # General status query
            result = self.query_status(
                query=query,
                station_data=context
            )
            return dspy.Prediction(
                answer=result.answer,
                data_summary=result.data_summary,
                confidence=result.confidence
            )

    def analyze_station_fault(
        self,
        fault_description: str,
        station_context: str,
        timestamp: str
    ) -> dspy.Prediction:
        """
        Dedicated method for fault event analysis.

        Args:
            fault_description: Description of the fault event
            station_context: Historical context for the station
            timestamp: When the fault occurred

        Returns:
            DSPy Prediction with fault analysis
        """
        return self.analyze_fault(
            fault_description=fault_description,
            station_context=station_context,
            timestamp=timestamp
        )

    def check_for_anomalies(
        self,
        current_metrics: str,
        baseline_metrics: str,
        station_id: str
    ) -> dspy.Prediction:
        """
        Check for performance anomalies.

        Args:
            current_metrics: Current performance data
            baseline_metrics: Historical baseline
            station_id: Station identifier

        Returns:
            DSPy Prediction with anomaly detection results
        """
        return self.detect_anomaly(
            current_metrics=current_metrics,
            baseline_metrics=baseline_metrics,
            station_id=station_id
        )

    def find_event_correlations(
        self,
        event_sequence: str,
        time_window: str = "24 hours"
    ) -> dspy.Prediction:
        """
        Find correlations in event sequences.

        Args:
            event_sequence: Sequence of events
            time_window: Time window for analysis

        Returns:
            DSPy Prediction with correlation results
        """
        return self.correlate_events(
            event_sequence=event_sequence,
            time_window=time_window
        )

    def check_load_balance(
        self,
        station_loads: str,
        time_period: str = "last 24 hours"
    ) -> dspy.Prediction:
        """
        Analyze load balance across stations.

        Args:
            station_loads: Load data for stations
            time_period: Analysis period

        Returns:
            DSPy Prediction with load balance analysis
        """
        return self.analyze_load(
            station_loads=station_loads,
            time_period=time_period
        )
