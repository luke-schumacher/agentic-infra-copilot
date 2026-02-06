"""
Illigo Operator Agent - Live Monitor (Port 8003)

Specialized agent for:
- OCPP event log analysis
- Anomaly detection in charging station data
- Real-time fault correlation
- Load balance monitoring

Components:
- brain.py: DSPy signatures for event analysis
- data_loader.py: Illigo PDF/CSV/event log loader
- vector_store.py: ChromaDB collection for station data
- main.py: FastAPI microservice

Author: Thesis Project - Agentic Infra Co-Pilot
"""

from src.agents.telemetry_agent.brain import IlligoOperatorModule
from src.agents.telemetry_agent.data_loader import IlligoLoader
from src.agents.telemetry_agent.vector_store import IlligoVectorStore

__all__ = [
    "IlligoOperatorModule",
    "IlligoLoader",
    "IlligoVectorStore"
]
