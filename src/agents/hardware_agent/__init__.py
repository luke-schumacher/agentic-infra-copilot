"""
Diagnostic Specialist Agent - Hardware Expert (Port 8002)

Specialized agent for:
- Hardware fault diagnosis
- Equipment specification lookup
- Technical documentation analysis
- MRI hardware data analysis

Components:
- brain.py: DSPy signatures for hardware reasoning
- mri_hardware_loader.py: MRI hardware data loader
- vector_store.py: ChromaDB collection for equipment data
- main.py: FastAPI microservice

Author: Thesis Project - Agentic Infra Co-Pilot
"""

from src.agents.hardware_agent.brain import DiagnosticSpecialistModule
from src.agents.hardware_agent.mri_hardware_loader import MRIHardwareLoader
from src.agents.hardware_agent.vector_store import DiagnosticSpecialistStore

__all__ = [
    "DiagnosticSpecialistModule",
    "MRIHardwareLoader",
    "DiagnosticSpecialistStore"
]
