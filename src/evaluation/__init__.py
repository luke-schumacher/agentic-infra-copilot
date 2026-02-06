"""
Evaluation Module - Automated Assessment for Multi-Agent System

Contains:
- judge.py: Agent-as-a-Judge for automated response evaluation
- metrics.py: Precision/Recall/F1 and semantic similarity metrics
- emergence_tests.py: Test case schemas for ablation testing
- diagnosis_logging.py: JSON logging for visualization
- ablation_runner.py: 5-mode ablation test runner

Author: Thesis Project - Agentic Infra Co-Pilot
"""

from src.evaluation.judge import AgentJudge, JudgeResult
from src.evaluation.metrics import SemanticMetrics, calculate_precision_recall_f1
from src.evaluation.emergence_tests import (
    EmergenceTestCase,
    EmergenceTestSuite,
    DEFAULT_TEST_SUITE,
    Difficulty
)
from src.evaluation.diagnosis_logging import (
    DiagnosisLog,
    RoundLog,
    CrossDomainReference,
    DiagnosisLogger
)
from src.evaluation.ablation_runner import (
    AblationTestRunner,
    AblationResult,
    AblationComparison,
    AblationMode
)

__all__ = [
    # Judge
    'AgentJudge',
    'JudgeResult',
    # Metrics
    'SemanticMetrics',
    'calculate_precision_recall_f1',
    # Emergence Tests
    'EmergenceTestCase',
    'EmergenceTestSuite',
    'DEFAULT_TEST_SUITE',
    'Difficulty',
    # Logging
    'DiagnosisLog',
    'RoundLog',
    'CrossDomainReference',
    'DiagnosisLogger',
    # Ablation
    'AblationTestRunner',
    'AblationResult',
    'AblationComparison',
    'AblationMode'
]
