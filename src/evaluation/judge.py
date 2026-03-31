"""
Agent-as-a-Judge - Automated Response Evaluation

Uses an LLM to evaluate agent responses against ground truth,
providing scores for accuracy, relevance, and completeness.

Best Practice: Automated evaluation scales better than manual review.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import logging
from dataclasses import dataclass
from typing import Optional

import dspy

from src.agents.shared.dspy_config import configure_dspy, get_lm_config

logger = logging.getLogger(__name__)


@dataclass
class JudgeResult:
    """Result from the Agent Judge evaluation."""
    accuracy_score: float      # 0-1: Factual correctness
    relevance_score: float     # 0-1: Relevance to query
    completeness_score: float  # 0-1: Response completeness
    cross_domain_score: float  # 0-1: Cross-domain synthesis quality
    overall_score: float       # Weighted average
    reasoning: str             # Explanation of scores
    passed: bool               # Whether meets threshold


class JudgeSignature(dspy.Signature):
    """
    Evaluate an agent's response against ground truth.

    You are an expert evaluator assessing the quality of an AI agent's
    response to an infrastructure diagnosis query. Pay special attention
    to whether the response synthesizes information across multiple domains
    (governance/SLA, hardware/equipment, telemetry/events).
    """
    query: str = dspy.InputField(desc="The original user query")
    agent_response: str = dspy.InputField(desc="The agent's response to evaluate")
    ground_truth: str = dspy.InputField(desc="The expected correct answer/diagnosis")
    expected_keywords: str = dspy.InputField(desc="Keywords that should appear in response")

    accuracy_score: float = dspy.OutputField(
        desc="Score 0.0-1.0: How factually correct is the response compared to ground truth?"
    )
    relevance_score: float = dspy.OutputField(
        desc="Score 0.0-1.0: How relevant is the response to the original query?"
    )
    completeness_score: float = dspy.OutputField(
        desc="Score 0.0-1.0: How complete is the response? Does it address all aspects?"
    )
    cross_domain_score: float = dspy.OutputField(
        desc="Score 0.0-1.0: Does the response synthesize information across multiple domains "
        "(governance, hardware, telemetry)? 0=single domain, 1=rich cross-domain synthesis"
    )
    reasoning: str = dspy.OutputField(
        desc="Brief explanation of the scores given (2-3 sentences)"
    )


class AgentJudge:
    """
    Agent-as-a-Judge for automated evaluation.

    Uses DSPy Chain-of-Thought to evaluate agent responses
    against ground truth with structured scoring.
    """

    def __init__(self, threshold: float = 0.6):
        """
        Initialize the Agent Judge.

        Args:
            threshold: Minimum overall score to pass (default 0.6)
        """
        self.threshold = threshold
        self._judge = None
        self._initialized = False

    def _lazy_init(self) -> bool:
        """Lazily initialize DSPy on first use."""
        if self._initialized:
            return self._judge is not None

        try:
            configure_dspy()
            lm_config = get_lm_config()
            self._sonnet_lm = lm_config.sonnet if lm_config else None
            self._judge = dspy.ChainOfThought(JudgeSignature)
            self._initialized = True
            logger.info("AgentJudge initialized with DSPy")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize AgentJudge: {e}")
            self._initialized = True
            return False

    def evaluate(
        self,
        query: str,
        agent_response: str,
        ground_truth: str,
        keywords: list[str] = None
    ) -> JudgeResult:
        """
        Evaluate an agent response.

        Args:
            query: Original user query
            agent_response: The agent's response to evaluate
            ground_truth: Expected correct answer
            keywords: List of keywords expected in response

        Returns:
            JudgeResult with scores and reasoning
        """
        if not self._lazy_init():
            # Fallback to keyword-based scoring if DSPy unavailable
            return self._fallback_evaluate(
                agent_response, ground_truth, keywords or []
            )

        try:
            # Prepare inputs
            keywords_str = ", ".join(keywords) if keywords else "none specified"

            # Run judge with Sonnet (higher quality evaluation)
            sonnet_lm = getattr(self, '_sonnet_lm', None)
            ctx = dspy.context(lm=sonnet_lm) if sonnet_lm else None
            if ctx:
                with ctx:
                    result = self._judge(
                        query=query,
                        agent_response=agent_response,
                        ground_truth=ground_truth,
                        expected_keywords=keywords_str
                    )
            else:
                result = self._judge(
                    query=query,
                    agent_response=agent_response,
                    ground_truth=ground_truth,
                    expected_keywords=keywords_str
                )

            # Parse scores (ensure 0-1 range)
            accuracy = self._parse_score(result.accuracy_score)
            relevance = self._parse_score(result.relevance_score)
            completeness = self._parse_score(result.completeness_score)
            cross_domain = self._parse_score(result.cross_domain_score)

            # Calculate weighted overall score
            overall = (
                accuracy * 0.35 +
                relevance * 0.2 +
                completeness * 0.2 +
                cross_domain * 0.25
            )

            return JudgeResult(
                accuracy_score=accuracy,
                relevance_score=relevance,
                completeness_score=completeness,
                cross_domain_score=cross_domain,
                overall_score=overall,
                reasoning=str(result.reasoning),
                passed=overall >= self.threshold
            )

        except Exception as e:
            logger.error(f"Judge evaluation failed: {e}")
            return self._fallback_evaluate(
                agent_response, ground_truth, keywords or []
            )

    def _parse_score(self, score) -> float:
        """Parse score to float in 0-1 range."""
        try:
            val = float(score)
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.5  # Default to middle score

    def _fallback_evaluate(
        self,
        response: str,
        ground_truth: str,
        keywords: list[str]
    ) -> JudgeResult:
        """
        Fallback evaluation using keyword matching.

        Used when DSPy is unavailable.
        """
        response_lower = response.lower()
        truth_lower = ground_truth.lower()

        # Keyword accuracy
        if keywords:
            keyword_hits = sum(1 for kw in keywords if kw.lower() in response_lower)
            accuracy = keyword_hits / len(keywords)
        else:
            # Simple word overlap
            truth_words = set(truth_lower.split())
            response_words = set(response_lower.split())
            overlap = len(truth_words & response_words)
            accuracy = overlap / max(len(truth_words), 1)

        # Relevance based on response length and content
        relevance = min(1.0, len(response) / 200)  # Penalize very short responses

        # Completeness based on keyword coverage
        completeness = accuracy  # Same as accuracy for fallback

        # Cross-domain: check for domain-specific terms
        domain_indicators = {
            'governance': ['sla', 'compliance', 'policy', 'uptime', 'contract'],
            'hardware': ['sensor', 'coil', 'amplifier', 'calibration', 'component'],
            'telemetry': ['event', 'pattern', 'log', 'anomaly', 'monitoring'],
        }
        domains_referenced = sum(
            1 for terms in domain_indicators.values()
            if any(t in response_lower for t in terms)
        )
        cross_domain = domains_referenced / 3.0

        overall = (
            accuracy * 0.35 +
            relevance * 0.2 +
            completeness * 0.2 +
            cross_domain * 0.25
        )

        return JudgeResult(
            accuracy_score=accuracy,
            relevance_score=relevance,
            completeness_score=completeness,
            cross_domain_score=cross_domain,
            overall_score=overall,
            reasoning="Fallback keyword-based evaluation (DSPy unavailable)",
            passed=overall >= self.threshold
        )

    def batch_evaluate(
        self,
        evaluations: list[dict]
    ) -> list[JudgeResult]:
        """
        Evaluate multiple responses.

        Args:
            evaluations: List of dicts with keys:
                - query, agent_response, ground_truth, keywords

        Returns:
            List of JudgeResults
        """
        results = []
        for eval_data in evaluations:
            result = self.evaluate(
                query=eval_data.get('query', ''),
                agent_response=eval_data.get('agent_response', ''),
                ground_truth=eval_data.get('ground_truth', ''),
                keywords=eval_data.get('keywords', [])
            )
            results.append(result)
        return results

    def get_summary_stats(self, results: list[JudgeResult]) -> dict:
        """
        Calculate summary statistics from multiple evaluations.

        Args:
            results: List of JudgeResults

        Returns:
            Dict with aggregate statistics
        """
        if not results:
            return {}

        n = len(results)
        return {
            'total_evaluated': n,
            'passed_count': sum(1 for r in results if r.passed),
            'pass_rate': sum(1 for r in results if r.passed) / n,
            'avg_accuracy': sum(r.accuracy_score for r in results) / n,
            'avg_relevance': sum(r.relevance_score for r in results) / n,
            'avg_completeness': sum(r.completeness_score for r in results) / n,
            'avg_cross_domain': sum(r.cross_domain_score for r in results) / n,
            'avg_overall': sum(r.overall_score for r in results) / n,
            'min_overall': min(r.overall_score for r in results),
            'max_overall': max(r.overall_score for r in results)
        }
