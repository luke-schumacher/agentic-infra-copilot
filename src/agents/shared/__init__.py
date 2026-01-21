"""
Shared utilities for all agents in the MAS architecture.

Contains:
- dspy_config.py: DSPy configuration with Groq LLM
- graph_service.py: Knowledge Graph access for hybrid search
- embeddings.py: Shared embedding configuration (future)

Author: Thesis Project - Agentic Infra Co-Pilot
"""

from src.agents.shared.graph_service import GraphService, get_graph_service

__all__ = ['GraphService', 'get_graph_service']
