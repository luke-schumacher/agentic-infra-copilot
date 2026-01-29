"""
Evaluation Metrics - Semantic Similarity and Classification Metrics

Provides:
- Semantic similarity using sentence embeddings
- Precision/Recall/F1 for classification tasks
- Keyword accuracy metrics

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import logging
from dataclasses import dataclass
from typing import List, Set, Tuple, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ClassificationMetrics:
    """Classification metrics for a single class or overall."""
    precision: float
    recall: float
    f1_score: float
    support: int  # Number of actual positives


class SemanticMetrics:
    """
    Semantic similarity metrics using sentence embeddings.

    Uses all-MiniLM-L6-v2 for fast, accurate similarity scoring.
    """

    def __init__(self):
        """Initialize the semantic metrics calculator."""
        self._model = None
        self._initialized = False

    def _lazy_init(self) -> bool:
        """Lazily load the embedding model."""
        if self._initialized:
            return self._model is not None

        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
            self._initialized = True
            logger.info("SemanticMetrics initialized with all-MiniLM-L6-v2")
            return True
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self._initialized = True
            return False

    def similarity(self, text1: str, text2: str) -> float:
        """
        Calculate cosine similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score between 0 and 1
        """
        if not self._lazy_init():
            # Fallback to Jaccard similarity
            return self._jaccard_similarity(text1, text2)

        try:
            emb1 = self._model.encode(text1, convert_to_numpy=True)
            emb2 = self._model.encode(text2, convert_to_numpy=True)

            # Cosine similarity
            dot_product = np.dot(emb1, emb2)
            norm1 = np.linalg.norm(emb1)
            norm2 = np.linalg.norm(emb2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)
            return float(max(0.0, min(1.0, similarity)))

        except Exception as e:
            logger.error(f"Semantic similarity failed: {e}")
            return self._jaccard_similarity(text1, text2)

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Fallback Jaccard similarity based on word overlap."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def batch_similarity(
        self,
        responses: List[str],
        ground_truths: List[str]
    ) -> List[float]:
        """
        Calculate similarity for multiple response-truth pairs.

        Args:
            responses: List of agent responses
            ground_truths: List of ground truth texts

        Returns:
            List of similarity scores
        """
        if len(responses) != len(ground_truths):
            raise ValueError("responses and ground_truths must have same length")

        return [
            self.similarity(resp, truth)
            for resp, truth in zip(responses, ground_truths)
        ]

    def average_similarity(
        self,
        responses: List[str],
        ground_truths: List[str]
    ) -> float:
        """Calculate average similarity across all pairs."""
        scores = self.batch_similarity(responses, ground_truths)
        return sum(scores) / len(scores) if scores else 0.0


def calculate_precision_recall_f1(
    predicted: List[str],
    actual: List[str],
    labels: Optional[List[str]] = None
) -> Tuple[ClassificationMetrics, dict]:
    """
    Calculate precision, recall, and F1 score.

    Args:
        predicted: List of predicted labels
        actual: List of actual/true labels
        labels: Optional list of all possible labels

    Returns:
        Tuple of (overall_metrics, per_class_metrics)
    """
    if len(predicted) != len(actual):
        raise ValueError("predicted and actual must have same length")

    # Get all unique labels
    all_labels = labels or list(set(predicted) | set(actual))

    # Per-class metrics
    per_class = {}
    for label in all_labels:
        tp = sum(1 for p, a in zip(predicted, actual) if p == label and a == label)
        fp = sum(1 for p, a in zip(predicted, actual) if p == label and a != label)
        fn = sum(1 for p, a in zip(predicted, actual) if p != label and a == label)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        support = sum(1 for a in actual if a == label)

        per_class[label] = ClassificationMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1,
            support=support
        )

    # Overall metrics (macro average)
    total_support = len(actual)
    macro_precision = sum(m.precision for m in per_class.values()) / len(per_class) if per_class else 0.0
    macro_recall = sum(m.recall for m in per_class.values()) / len(per_class) if per_class else 0.0
    macro_f1 = sum(m.f1_score for m in per_class.values()) / len(per_class) if per_class else 0.0

    overall = ClassificationMetrics(
        precision=macro_precision,
        recall=macro_recall,
        f1_score=macro_f1,
        support=total_support
    )

    return overall, per_class


def keyword_accuracy(
    response: str,
    keywords: List[str],
    case_sensitive: bool = False
) -> Tuple[float, List[str], List[str]]:
    """
    Calculate keyword accuracy for a response.

    Args:
        response: The response text to check
        keywords: List of keywords that should appear
        case_sensitive: Whether matching is case-sensitive

    Returns:
        Tuple of (accuracy, found_keywords, missing_keywords)
    """
    if not keywords:
        return 1.0, [], []

    check_text = response if case_sensitive else response.lower()
    check_keywords = keywords if case_sensitive else [k.lower() for k in keywords]

    found = [kw for kw in check_keywords if kw in check_text]
    missing = [kw for kw in check_keywords if kw not in check_text]

    accuracy = len(found) / len(keywords)

    return accuracy, found, missing


def delegation_accuracy(
    predicted_delegations: List[str],
    expected_delegations: List[str]
) -> Tuple[float, int, int]:
    """
    Calculate delegation routing accuracy.

    Args:
        predicted_delegations: List of predicted delegation targets
        expected_delegations: List of expected delegation targets

    Returns:
        Tuple of (accuracy, correct_count, total_count)
    """
    if len(predicted_delegations) != len(expected_delegations):
        raise ValueError("Lists must have same length")

    correct = sum(
        1 for p, e in zip(predicted_delegations, expected_delegations)
        if p.lower().strip() == e.lower().strip()
    )

    total = len(expected_delegations)
    accuracy = correct / total if total > 0 else 0.0

    return accuracy, correct, total


def risk_level_accuracy(
    predicted_risks: List[str],
    actual_risks: List[str]
) -> Tuple[float, dict]:
    """
    Calculate risk level classification accuracy.

    Args:
        predicted_risks: List of predicted risk levels
        actual_risks: List of actual risk levels

    Returns:
        Tuple of (accuracy, confusion_matrix_dict)
    """
    risk_levels = ['low', 'medium', 'high', 'critical']

    # Normalize inputs
    pred_norm = [r.lower().strip() for r in predicted_risks]
    actual_norm = [r.lower().strip() for r in actual_risks]

    # Calculate accuracy
    correct = sum(1 for p, a in zip(pred_norm, actual_norm) if p == a)
    accuracy = correct / len(actual_norm) if actual_norm else 0.0

    # Build confusion matrix
    confusion = {level: {l: 0 for l in risk_levels} for level in risk_levels}
    for pred, actual in zip(pred_norm, actual_norm):
        if pred in risk_levels and actual in risk_levels:
            confusion[actual][pred] += 1

    return accuracy, confusion


# ============================================================================
# CooperBench-Inspired Metrics for Multi-Agent Evaluation
# Added for thesis RQ2 evaluation: Single-Agent vs Multi-Agent comparison
# ============================================================================

@dataclass
class CommunicationOverhead:
    """Metrics for measuring inter-agent communication overhead."""
    delegation_count: int
    total_delegation_time_ms: float
    avg_delegation_time_ms: float
    delegation_success_rate: float
    overhead_ratio: float  # delegation_time / total_time


def calculate_communication_overhead(
    response: dict,
    total_processing_time_ms: float
) -> CommunicationOverhead:
    """
    Calculate communication overhead for multi-agent coordination.

    Measures time and resources spent on inter-agent delegation,
    inspired by CooperBench's coordination overhead analysis.

    Args:
        response: Full response dict from Minister agent
        total_processing_time_ms: Total query processing time

    Returns:
        CommunicationOverhead dataclass with metrics
    """
    delegation_count = 0
    delegation_time_ms = 0.0
    delegation_successes = 0

    if not response:
        return CommunicationOverhead(
            delegation_count=0,
            total_delegation_time_ms=0.0,
            avg_delegation_time_ms=0.0,
            delegation_success_rate=0.0,
            overhead_ratio=0.0
        )

    response_card = response.get('response_card', {})
    payload = response_card.get('payload', {})

    # Check if delegation occurred
    delegation = payload.get('delegation', {})
    target = delegation.get('target_agent', 'self')
    skipped = delegation.get('skipped', False)

    if target and target != 'self' and not skipped:
        delegation_count = 1

        # Check if specialist findings exist (successful delegation)
        specialist = payload.get('specialist_findings')
        if specialist and isinstance(specialist, dict):
            delegation_successes = 1

            # Extract specialist processing time if available
            spec_time = specialist.get('processing_time_ms', 0)
            if spec_time:
                delegation_time_ms = float(spec_time)
            else:
                # Estimate: assume delegation takes ~40% of total time
                delegation_time_ms = total_processing_time_ms * 0.4

    avg_time = delegation_time_ms / delegation_count if delegation_count > 0 else 0.0
    success_rate = delegation_successes / delegation_count if delegation_count > 0 else 1.0
    overhead = delegation_time_ms / total_processing_time_ms if total_processing_time_ms > 0 else 0.0

    return CommunicationOverhead(
        delegation_count=delegation_count,
        total_delegation_time_ms=delegation_time_ms,
        avg_delegation_time_ms=avg_time,
        delegation_success_rate=success_rate,
        overhead_ratio=overhead
    )


def cross_domain_resolution_rate(
    response: str,
    required_domains: List[str]
) -> Tuple[float, List[str], List[str]]:
    """
    Calculate cross-domain resolution rate.

    Measures what percentage of required domains are addressed in the response.
    Critical for evaluating RQ2: effectiveness of cross-domain reasoning.

    Args:
        response: Full response text (combined from all agents)
        required_domains: List of domains needed for complete resolution
                         ('governance', 'hardware', 'operations')

    Returns:
        Tuple of (resolution_rate, domains_covered, domains_missing)
    """
    response_lower = response.lower()
    domains_covered = []
    domains_missing = []

    # Domain-specific marker detection
    domain_markers = {
        'governance': [
            'sla', 'policy', 'compliance', 'governance', 'regulation',
            'int-', 'intent', 'violation', 'threshold', 'requirement'
        ],
        'hardware': [
            'equipment', 'hardware', 'component', 'fm-', 'vs-',
            'failure mode', 'specification', 'cable', 'connector',
            'rcd', 'mcb', 'meter', 'sensor'
        ],
        'operations': [
            'station', 'session', 'charging', 'fault event', 'connector',
            'ocpp', 'kwh', 'energy', 'load', 'anomaly', 'telemetry'
        ]
    }

    for domain in required_domains:
        markers = domain_markers.get(domain, [])
        if any(marker in response_lower for marker in markers):
            domains_covered.append(domain)
        else:
            domains_missing.append(domain)

    rate = len(domains_covered) / len(required_domains) if required_domains else 1.0

    return rate, domains_covered, domains_missing


@dataclass
class IntegrationScore:
    """Score for information integration quality."""
    coherence_score: float  # How well information is connected
    completeness_score: float  # Coverage of required information
    synthesis_score: float  # Quality of combining multiple sources
    overall_score: float


def information_integration_score(
    minister_response: dict,
    specialist_responses: Optional[List[dict]] = None,
    ground_truth: Optional[dict] = None
) -> IntegrationScore:
    """
    Calculate information integration quality score.

    Measures how well the Minister agent integrates specialist findings
    into a coherent, complete response. Key metric for multi-agent evaluation.

    Args:
        minister_response: Minister's full response
        specialist_responses: List of specialist agent responses
        ground_truth: Optional expected answer for completeness check

    Returns:
        IntegrationScore with component and overall scores
    """
    if not minister_response:
        return IntegrationScore(
            coherence_score=0.0,
            completeness_score=0.0,
            synthesis_score=0.0,
            overall_score=0.0
        )

    response_card = minister_response.get('response_card', {})
    payload = response_card.get('payload', {})

    # 1. Coherence: Check if response has logical structure
    coherence_markers = [
        'root cause', 'because', 'therefore', 'due to',
        'recommendation', 'action', 'next step'
    ]

    response_text = " ".join([
        str(payload.get('answer', '')),
        str(payload.get('risk_level', '')),
        str(payload.get('violated_slas', '')),
        str(payload.get('recommended_actions', '')),
    ]).lower()

    coherence_hits = sum(1 for m in coherence_markers if m in response_text)
    coherence_score = min(1.0, coherence_hits / 3)  # Expect at least 3 markers

    # 2. Completeness: Check specialist findings integration
    specialist_findings = payload.get('specialist_findings')
    completeness_score = 0.5  # Base score

    if specialist_findings and isinstance(specialist_findings, dict):
        # Successfully integrated specialist response
        completeness_score = 0.8

        spec_card = specialist_findings.get('response_card', {})
        spec_payload = spec_card.get('payload', {})

        # Check if specialist content is reflected in main response
        spec_content = str(spec_payload.get('diagnosis', '')) + str(spec_payload.get('root_cause', ''))

        if spec_content:
            # Extract key terms from specialist
            spec_words = set(spec_content.lower().split())
            response_words = set(response_text.split())

            overlap = len(spec_words & response_words)
            if overlap >= 3:
                completeness_score = 1.0

    # 3. Synthesis: Check if multiple data sources are referenced
    synthesis_markers = [
        'according to', 'based on', 'from', 'analysis shows',
        'indicates', 'suggests', 'source'
    ]

    synthesis_hits = sum(1 for m in synthesis_markers if m in response_text)
    synthesis_score = min(1.0, synthesis_hits / 2)  # Expect at least 2 references

    # Check documents referenced
    documents = response_card.get('documents', [])
    if len(documents) >= 3:
        synthesis_score = min(1.0, synthesis_score + 0.3)

    # Overall weighted score
    overall = (
        0.30 * coherence_score +
        0.40 * completeness_score +
        0.30 * synthesis_score
    )

    return IntegrationScore(
        coherence_score=coherence_score,
        completeness_score=completeness_score,
        synthesis_score=synthesis_score,
        overall_score=overall
    )


def cooperation_effectiveness(
    baseline_results: List[dict],
    multi_agent_results: List[dict]
) -> dict:
    """
    Calculate cooperation effectiveness metrics.

    Inspired by CooperBench's finding that coordinating agents often
    perform worse than single agents. This metric identifies WHERE
    multi-agent cooperation provides value.

    Args:
        baseline_results: List of scenario results from single-agent
        multi_agent_results: List of scenario results from multi-agent

    Returns:
        Dictionary with cooperation effectiveness analysis
    """
    if len(baseline_results) != len(multi_agent_results):
        raise ValueError("Result lists must have same length")

    n = len(baseline_results)

    # Per-scenario comparison
    multi_agent_wins = 0
    baseline_wins = 0
    ties = 0

    accuracy_improvements = []
    mtti_differences = []

    for baseline, multi in zip(baseline_results, multi_agent_results):
        b_acc = baseline.get('keyword_accuracy', 0)
        m_acc = multi.get('keyword_accuracy', 0)

        if m_acc > b_acc:
            multi_agent_wins += 1
        elif b_acc > m_acc:
            baseline_wins += 1
        else:
            ties += 1

        accuracy_improvements.append(m_acc - b_acc)

        b_mtti = baseline.get('mtti_seconds', 0)
        m_mtti = multi.get('mtti_seconds', 0)
        mtti_differences.append(m_mtti - b_mtti)

    # Calculate cooperation benefit ratio
    cooperation_benefit = multi_agent_wins / n if n > 0 else 0

    # Identify scenario characteristics where multi-agent wins
    avg_improvement = sum(accuracy_improvements) / n if n > 0 else 0
    avg_mtti_overhead = sum(mtti_differences) / n if n > 0 else 0

    return {
        "scenario_count": n,
        "multi_agent_wins": multi_agent_wins,
        "baseline_wins": baseline_wins,
        "ties": ties,
        "cooperation_benefit_ratio": cooperation_benefit,
        "avg_accuracy_improvement": avg_improvement,
        "avg_mtti_overhead_seconds": avg_mtti_overhead,
        "recommendation": (
            "Multi-agent preferred" if cooperation_benefit > 0.6
            else "Baseline preferred" if cooperation_benefit < 0.4
            else "Context-dependent"
        )
    }
