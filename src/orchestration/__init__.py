"""
Orchestration Module - Multi-Round Agent Dialogue

Manages multi-round diagnosis sessions across agents, implementing
the emergence-enabling dialogue protocol from the design document.

Components:
- MultiRoundOrchestrator: Main orchestration logic
- Round handling for ANSWER, PARTIAL, CLARIFY, REDIRECT, REFUSE, CONSULT
"""

from src.orchestration.multi_round import MultiRoundOrchestrator
from src.orchestration.synthesis import DiagnosisSynthesizer

__all__ = ['MultiRoundOrchestrator', 'DiagnosisSynthesizer']
