"""
Siemens Technician Agent - Hardware Expert (Port 8002)

Specialized agent for:
- Hardware fault diagnosis
- Equipment specification lookup
- Technical documentation analysis
- Pain point analysis from questionnaire data

Components:
- brain.py: DSPy signatures for hardware reasoning
- data_loader.py: Siemens CSV questionnaire loader
- vector_store.py: ChromaDB collection for equipment data
- main.py: FastAPI microservice

Author: Thesis Project - Agentic Infra Co-Pilot
"""

from src.agents.hardware_agent.brain import SiemensTechnicianModule
from src.agents.hardware_agent.data_loader import SiemensLoader
from src.agents.hardware_agent.vector_store import SiemensVectorStore

__all__ = [
    "SiemensTechnicianModule",
    "SiemensLoader",
    "SiemensVectorStore"
]
