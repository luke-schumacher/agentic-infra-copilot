"""
Diagnosis Synthesizer - DSPy-based Integration of Multi-Agent Findings

Replaces the concatenation-based finalization in multi_round.py with
genuine LLM reasoning over agent findings. Uses ChainOfThought to
produce a single, unified diagnosis from multiple specialist perspectives.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import logging
import dspy
from src.agents.shared.dspy_config import configure_dspy, get_lm_config

logger = logging.getLogger(__name__)


class SynthesizeDiagnosis(dspy.Signature):
    """Synthesize findings from multiple specialist agents into one unified diagnosis."""
    original_query: str = dspy.InputField(desc="The original diagnostic query")
    agent_findings: str = dspy.InputField(desc="Labeled findings from each specialist agent")
    unified_diagnosis: str = dspy.OutputField(
        desc="Concise integrated root-cause diagnosis with cross-domain connections "
             "and recommended actions in under 300 words"
    )


class DiagnosisSynthesizer:
    """
    Synthesizes multi-agent findings into a unified diagnosis using DSPy ChainOfThought.

    Unlike the previous _run_synthesis_round() which called the Governance Agent
    (triggering fresh RAG retrieval), this module performs pure LLM reasoning over
    the provided evidence — no HTTP calls, no vector store queries.
    """

    def __init__(self):
        # Ensure DSPy is configured (idempotent if already configured by agents)
        if dspy.settings.lm is None:
            configure_dspy()
        lm_config = get_lm_config()
        self._sonnet_lm = lm_config.sonnet if lm_config else None
        self._synthesizer = dspy.ChainOfThought(SynthesizeDiagnosis)

    def synthesize(self, query: str, findings_dict: dict[str, str]) -> str:
        """
        Synthesize agent findings into a unified diagnosis.

        Args:
            query: The original diagnostic query
            findings_dict: Mapping of agent_id -> findings text
                e.g. {"governance_agent": "...", "hardware_agent": "..."}

        Returns:
            Unified diagnosis string. Falls back to concatenation on failure.
        """
        if not findings_dict:
            return "No agent findings available for synthesis."

        # Format findings with clear agent labels
        formatted_findings = "\n\n".join(
            f"[{agent_id}]: {findings}"
            for agent_id, findings in findings_dict.items()
            if findings
        )

        if not formatted_findings:
            return "No substantive findings from any agent."

        try:
            # Use Sonnet for cross-domain synthesis (higher quality than Haiku default)
            ctx = dspy.context(lm=self._sonnet_lm) if self._sonnet_lm else None
            if ctx:
                with ctx:
                    result = self._synthesizer(
                        original_query=query,
                        agent_findings=formatted_findings
                    )
            else:
                result = self._synthesizer(
                    original_query=query,
                    agent_findings=formatted_findings
                )
            synthesis = result.unified_diagnosis

            if synthesis and len(synthesis.strip()) > 20:
                logger.info(
                    "Synthesis produced unified diagnosis "
                    f"({len(synthesis)} chars from {len(findings_dict)} agents)"
                )
                return synthesis
            else:
                logger.warning("Synthesis produced insufficient output, falling back to concatenation")
                return self._fallback_concatenation(findings_dict)

        except Exception as e:
            logger.error(f"Synthesis failed ({e}), falling back to concatenation")
            return self._fallback_concatenation(findings_dict)

    @staticmethod
    def _fallback_concatenation(findings_dict: dict[str, str]) -> str:
        """Fallback: concatenate findings (preserves pre-fix behavior)."""
        parts = []
        for agent_id, findings in findings_dict.items():
            if findings:
                parts.append(f"{agent_id}: {findings}")
        return "\n".join(parts) if parts else "No findings available."
