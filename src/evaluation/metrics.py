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
