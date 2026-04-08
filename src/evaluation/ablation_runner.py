"""
Ablation Test Runner - MAS vs Single-Agent Comparison

Runs each test case in five modes to prove emergence:
1. Governance Only - Single agent with governance data
2. Hardware Only - Single agent with hardware data
3. Telemetry Only - Single agent with telemetry data
4. Single + All Data - One agent with all three data sources
5. MAS (Full) - All agents collaborating

Emergence is demonstrated when:
    MAS accuracy > max(ablation accuracies) AND
    MAS produces reasoning chains that reference multiple domains

Per design doc section 6 - Evaluation Framework.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import json
from pydantic import BaseModel, Field

from src.evaluation.emergence_tests import (
    EmergenceTestCase,
    EmergenceTestSuite,
    DEFAULT_TEST_SUITE,
    Difficulty
)
from src.evaluation.diagnosis_logging import (
    DiagnosisLog,
    RoundLog,
    DiagnosisLogger
)
from src.evaluation.judge import AgentJudge
from src.evaluation.metrics import SemanticMetrics
from src.orchestration.multi_round import MultiRoundOrchestrator
from src.protocol.schema import DiagnosisSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AblationMode:
    """Ablation test modes."""
    GOVERNANCE_ONLY = "governance_only"
    HARDWARE_ONLY = "hardware_only"
    TELEMETRY_ONLY = "telemetry_only"
    SINGLE_ALL_DATA = "single_all_data"
    MAS_FULL = "mas_full"

    ALL_MODES = [
        GOVERNANCE_ONLY,
        HARDWARE_ONLY,
        TELEMETRY_ONLY,
        SINGLE_ALL_DATA,
        MAS_FULL
    ]


class AblationResult(BaseModel):
    """Result from a single ablation run."""
    test_case_name: str
    mode: str
    diagnosis: str
    confidence: float
    accuracy_score: float = Field(
        description="0.0-1.0 match to ground truth"
    )
    keyword_matches: int = Field(
        description="Count of required keywords found"
    )
    total_keywords: int = Field(
        description="Total required keywords"
    )
    rounds_used: int
    latency_ms: float
    agents_consulted: List[str]
    cross_domain_refs: int = Field(
        description="Number of cross-domain references (emergence indicator)"
    )
    emergence_detected: bool = Field(
        description="True if reasoning spans multiple domains"
    )
    judge_scores: Optional[Dict[str, float]] = Field(
        default=None, description="LLM-as-Judge scores"
    )
    semantic_score: Optional[float] = Field(
        default=None, description="Semantic similarity 0.0-1.0"
    )

    @property
    def keyword_accuracy(self) -> float:
        """Percentage of required keywords found."""
        if self.total_keywords == 0:
            return 1.0
        return self.keyword_matches / self.total_keywords


class AblationComparison(BaseModel):
    """Comparison of all ablation modes for a test case."""
    test_case_name: str
    test_case_difficulty: str
    results: Dict[str, AblationResult]

    # Summary metrics
    best_single_agent_accuracy: float = 0.0
    mas_accuracy: float = 0.0
    emergence_margin: float = Field(
        default=0.0,
        description="MAS accuracy - best single agent accuracy"
    )
    emergence_demonstrated: bool = Field(
        default=False,
        description="True if MAS outperforms all single agents"
    )

    def calculate_emergence(self) -> None:
        """
        Calculate emergence metrics.

        Emergence criterion:
            MAS accuracy > best single agent accuracy
            AND (cross_domain_refs > 0 OR judge cross_domain score > 0.5)

        This dual criterion prevents false negatives from fragile keyword
        detection by also accepting the LLM-as-Judge's cross-domain assessment.
        """
        single_modes = [
            AblationMode.GOVERNANCE_ONLY,
            AblationMode.HARDWARE_ONLY,
            AblationMode.TELEMETRY_ONLY,
            AblationMode.SINGLE_ALL_DATA
        ]

        single_accuracies = [
            self.results[mode].accuracy_score
            for mode in single_modes
            if mode in self.results
        ]

        if single_accuracies:
            self.best_single_agent_accuracy = max(single_accuracies)

        if AblationMode.MAS_FULL in self.results:
            self.mas_accuracy = self.results[AblationMode.MAS_FULL].accuracy_score
            mas_result = self.results[AblationMode.MAS_FULL]

            self.emergence_margin = self.mas_accuracy - self.best_single_agent_accuracy

            # Check cross-domain evidence from two sources
            has_cross_domain_refs = mas_result.cross_domain_refs > 0
            judge_cross_domain = (
                mas_result.judge_scores.get('cross_domain', 0.0)
                if mas_result.judge_scores else 0.0
            )
            has_judge_cross_domain = judge_cross_domain > 0.5

            # Emergence requires margin > 0 AND at least one cross-domain signal
            self.emergence_demonstrated = (
                self.emergence_margin > 0 and
                (has_cross_domain_refs or has_judge_cross_domain)
            )


class AblationTestRunner:
    """
    Runs ablation tests across all modes.

    For each test case:
    1. Run governance-only (only governance context)
    2. Run hardware-only (only hardware context)
    3. Run telemetry-only (only telemetry context)
    4. Run single-agent with all data
    5. Run full MAS collaboration

    Compare results to prove emergence.
    """

    def __init__(
        self,
        orchestrator: Optional[MultiRoundOrchestrator] = None,
        log_dir: str = "results/ablation"
    ):
        """
        Initialize runner.

        Args:
            orchestrator: Optional pre-configured orchestrator
            log_dir: Directory for result files
        """
        self.orchestrator = orchestrator or MultiRoundOrchestrator(confidence_threshold=0.5)
        self.logger = DiagnosisLogger(log_dir)
        self.results_dir = Path(log_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.judge = AgentJudge(threshold=0.6)
        self.semantic_metrics = SemanticMetrics()

    def _calculate_accuracy(
        self,
        diagnosis: str,
        test_case: EmergenceTestCase
    ) -> Tuple[float, int]:
        """
        Calculate accuracy score based on keyword matching.

        Args:
            diagnosis: Generated diagnosis
            test_case: Test case with ground truth

        Returns:
            Tuple of (accuracy_score, keyword_matches)
        """
        diagnosis_lower = diagnosis.lower()
        matches = 0

        for keyword in test_case.required_keywords:
            if keyword.lower() in diagnosis_lower:
                matches += 1

        accuracy = matches / len(test_case.required_keywords) if test_case.required_keywords else 1.0
        return accuracy, matches

    def _evaluate_with_judge_and_semantics(
        self,
        diagnosis: str,
        test_case: EmergenceTestCase
    ) -> Tuple[Optional[Dict[str, float]], Optional[float]]:
        """
        Evaluate diagnosis with LLM-as-Judge and semantic similarity.

        Returns:
            Tuple of (judge_scores_dict, semantic_score) with fallbacks to None
        """
        judge_scores = None
        semantic_score = None

        try:
            judge_result = self.judge.evaluate(
                query=test_case.description,
                agent_response=diagnosis,
                ground_truth=test_case.emergent_diagnosis,
                keywords=test_case.required_keywords
            )
            judge_scores = {
                'accuracy': judge_result.accuracy_score,
                'relevance': judge_result.relevance_score,
                'completeness': judge_result.completeness_score,
                'cross_domain': judge_result.cross_domain_score,
                'overall_score': judge_result.overall_score,
            }
        except Exception as e:
            logger.warning(f"Judge evaluation failed: {e}")

        try:
            semantic_score = self.semantic_metrics.similarity(
                diagnosis, test_case.emergent_diagnosis
            )
        except Exception as e:
            logger.warning(f"Semantic similarity failed: {e}")

        return judge_scores, semantic_score

    async def _run_single_agent_mode(
        self,
        test_case: EmergenceTestCase,
        mode: str,
        context: str
    ) -> AblationResult:
        """
        Run a single-agent ablation mode.

        In single-agent mode, we call only one agent with limited context.
        """
        start_time = time.time()

        # Determine which agent to use
        agent_map = {
            AblationMode.GOVERNANCE_ONLY: 'governance_agent',
            AblationMode.HARDWARE_ONLY: 'hardware_agent',
            AblationMode.TELEMETRY_ONLY: 'telemetry_agent'
        }

        agent_id = agent_map.get(mode, 'governance_agent')

        # For single-agent mode, call agent directly with limited context
        explicit_context = (
            f"You are given the following domain data. "
            f"Use ONLY this information to diagnose the issue:\n\n{context}"
        )
        try:
            response, latency = await self.orchestrator._call_agent(
                agent_id,
                f"{test_case.description}\n\n{explicit_context}",
                explicit_context
            )

            diagnosis = response.findings or f"No findings from {agent_id}"
            confidence = response.confidence

        except Exception as e:
            logger.error(f"Error in single-agent mode {mode}: {e}")
            diagnosis = f"Error: {str(e)}"
            confidence = 0.0
            latency = 0.0

        latency_ms = (time.time() - start_time) * 1000
        accuracy, keyword_matches = self._calculate_accuracy(diagnosis, test_case)
        judge_scores, semantic_score = self._evaluate_with_judge_and_semantics(diagnosis, test_case)

        return AblationResult(
            test_case_name=test_case.name,
            mode=mode,
            diagnosis=diagnosis,
            confidence=confidence,
            accuracy_score=accuracy,
            keyword_matches=keyword_matches,
            total_keywords=len(test_case.required_keywords),
            rounds_used=1,
            latency_ms=latency_ms,
            agents_consulted=[agent_id],
            cross_domain_refs=0,  # Single agent can't have cross-domain refs
            emergence_detected=False,
            judge_scores=judge_scores,
            semantic_score=semantic_score
        )

    def _is_empty_response(self, text: str) -> bool:
        """Check if a response is empty or useless."""
        if not text:
            return True
        stripped = text.strip().lower()
        return stripped in ("", "no findings", "no findings.", "error", "n/a") or stripped.startswith("error:")

    async def _run_single_all_data_mode(
        self,
        test_case: EmergenceTestCase
    ) -> AblationResult:
        """
        Run single agent with all context combined.

        Tries agents sequentially (governance → hardware → telemetry) with
        combined context. Uses the first agent that returns a real response.
        Fallback: hardware agent (most reliable in current setup).
        """
        start_time = time.time()

        # Combine all contexts with explicit instruction
        combined_context = f"""You are given the following domain data. Use ONLY this information to diagnose the issue:

Governance Context:
{test_case.governance_context}

Hardware Context:
{test_case.hardware_context}

Telemetry Context:
{test_case.telemetry_context}
"""

        # Try agents in order: governance → hardware → telemetry
        agent_order = ['governance_agent', 'hardware_agent', 'telemetry_agent']
        diagnosis = "No findings"
        confidence = 0.0
        agent_used = agent_order[0]

        for agent_id in agent_order:
            try:
                response, latency = await self.orchestrator._call_agent(
                    agent_id,
                    test_case.description,
                    combined_context
                )

                candidate = response.findings or ""
                if not self._is_empty_response(candidate):
                    diagnosis = candidate
                    confidence = response.confidence
                    agent_used = agent_id
                    logger.info(f"single_all_data: {agent_id} returned valid response")
                    break
                else:
                    logger.warning(f"single_all_data: {agent_id} returned empty/no-findings, trying next agent")

            except Exception as e:
                logger.warning(f"single_all_data: {agent_id} failed ({e}), trying next agent")

        latency_ms = (time.time() - start_time) * 1000
        accuracy, keyword_matches = self._calculate_accuracy(diagnosis, test_case)
        judge_scores, semantic_score = self._evaluate_with_judge_and_semantics(diagnosis, test_case)

        return AblationResult(
            test_case_name=test_case.name,
            mode=AblationMode.SINGLE_ALL_DATA,
            diagnosis=diagnosis,
            confidence=confidence,
            accuracy_score=accuracy,
            keyword_matches=keyword_matches,
            total_keywords=len(test_case.required_keywords),
            rounds_used=1,
            latency_ms=latency_ms,
            agents_consulted=[agent_used],
            cross_domain_refs=0,
            emergence_detected=False,
            judge_scores=judge_scores,
            semantic_score=semantic_score
        )

    async def _run_mas_full_mode(
        self,
        test_case: EmergenceTestCase
    ) -> AblationResult:
        """
        Run full MAS with all agents collaborating.

        This is the target mode that should demonstrate emergence.
        """
        start_time = time.time()

        try:
            session = await self.orchestrator.run_diagnosis(
                query=(
                    f"{test_case.description}\n\n"
                    f"Governance context: {test_case.governance_context}\n\n"
                    f"Hardware context: {test_case.hardware_context}\n\n"
                    f"Telemetry context: {test_case.telemetry_context}\n\n"
                    f"IMPORTANT: This scenario requires cross-domain analysis. "
                    f"Consult hardware and telemetry specialists — they hold data "
                    f"not available in governance records."
                ),
                location="Test Environment",
                equipment_type="MRI"
            )

            diagnosis = session.final_diagnosis or "No diagnosis"
            confidence = session.current_confidence

            # Create log for detailed analysis
            log = DiagnosisLog(
                session_id=session.session_id,
                test_case_id=test_case.name,
                mode=AblationMode.MAS_FULL,
                original_query=test_case.description,
                final_diagnosis=diagnosis,
                ground_truth=test_case.emergent_diagnosis,
                termination_reason=session.termination_reason or "unknown",
                agents_consulted=session.agents_consulted
            )

            # Add rounds from session (pass full findings for cross-domain detection)
            for i, resp in enumerate(session.agent_responses):
                log.add_round(RoundLog(
                    round_number=i,
                    agent=resp.agent_id,
                    response_type=resp.response_type.value,
                    confidence=resp.confidence,
                    findings_summary=resp.findings if resp.findings else "",
                    latency_ms=0  # Not tracked per-round
                ))

            log.detect_cross_domain_references()
            self.logger.save_log(log)

            cross_domain_refs = len(log.cross_domain_refs)

        except Exception as e:
            logger.error(f"Error in MAS full mode: {e}")
            diagnosis = f"Error: {str(e)}"
            confidence = 0.0
            session = None
            cross_domain_refs = 0

        latency_ms = (time.time() - start_time) * 1000
        accuracy, keyword_matches = self._calculate_accuracy(diagnosis, test_case)
        judge_scores, semantic_score = self._evaluate_with_judge_and_semantics(diagnosis, test_case)

        return AblationResult(
            test_case_name=test_case.name,
            mode=AblationMode.MAS_FULL,
            diagnosis=diagnosis,
            confidence=confidence,
            accuracy_score=accuracy,
            keyword_matches=keyword_matches,
            total_keywords=len(test_case.required_keywords),
            rounds_used=session.current_round if session else 0,
            latency_ms=latency_ms,
            agents_consulted=session.agents_consulted if session else [],
            cross_domain_refs=cross_domain_refs,
            emergence_detected=cross_domain_refs > 0 and accuracy > 0.5,
            judge_scores=judge_scores,
            semantic_score=semantic_score
        )

    async def run_ablation(
        self,
        test_case: EmergenceTestCase
    ) -> AblationComparison:
        """
        Run all ablation modes for a single test case.

        Args:
            test_case: Test case to evaluate

        Returns:
            AblationComparison with results from all modes
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Running Ablation: {test_case.name}")
        logger.info(f"{'='*60}")

        results = {}
        # 10 s between modes lets the Anthropic token-budget window partially refill
        # before the next (heavier) mode fires — especially important before MAS which
        # fires parallel agent calls and synthesis in rapid succession.
        inter_mode_delay = 10  # seconds between modes to avoid Anthropic/OpenAI rate limits

        # Mode 1: Governance Only
        logger.info("Running governance_only mode...")
        results[AblationMode.GOVERNANCE_ONLY] = await self._run_single_agent_mode(
            test_case,
            AblationMode.GOVERNANCE_ONLY,
            test_case.governance_context
        )

        await asyncio.sleep(inter_mode_delay)

        # Mode 2: Hardware Only
        logger.info("Running hardware_only mode...")
        results[AblationMode.HARDWARE_ONLY] = await self._run_single_agent_mode(
            test_case,
            AblationMode.HARDWARE_ONLY,
            test_case.hardware_context
        )

        await asyncio.sleep(inter_mode_delay)

        # Mode 3: Telemetry Only
        logger.info("Running telemetry_only mode...")
        results[AblationMode.TELEMETRY_ONLY] = await self._run_single_agent_mode(
            test_case,
            AblationMode.TELEMETRY_ONLY,
            test_case.telemetry_context
        )

        await asyncio.sleep(inter_mode_delay)

        # Mode 4: Single + All Data
        logger.info("Running single_all_data mode...")
        results[AblationMode.SINGLE_ALL_DATA] = await self._run_single_all_data_mode(
            test_case
        )

        await asyncio.sleep(inter_mode_delay)

        # Mode 5: MAS Full
        logger.info("Running mas_full mode...")
        results[AblationMode.MAS_FULL] = await self._run_mas_full_mode(
            test_case
        )

        comparison = AblationComparison(
            test_case_name=test_case.name,
            test_case_difficulty=test_case.difficulty.value,
            results=results
        )
        comparison.calculate_emergence()

        return comparison

    async def run_all_test_cases(
        self,
        test_suite: Optional[EmergenceTestSuite] = None
    ) -> List[AblationComparison]:
        """
        Run ablation for all test cases in suite.

        Args:
            test_suite: Test suite to run (defaults to DEFAULT_TEST_SUITE)

        Returns:
            List of AblationComparison results
        """
        suite = test_suite or DEFAULT_TEST_SUITE
        comparisons = []

        for test_case in suite.test_cases:
            comparison = await self.run_ablation(test_case)
            comparisons.append(comparison)

            # Save intermediate results
            self._save_comparison(comparison)

        # Save summary
        self._save_summary(comparisons)

        return comparisons

    def _save_comparison(self, comparison: AblationComparison) -> None:
        """Save single comparison to file."""
        filepath = self.results_dir / f"{comparison.test_case_name}_ablation.json"
        with open(filepath, 'w') as f:
            json.dump(comparison.model_dump(), f, indent=2)
        logger.info(f"Saved comparison: {filepath}")

    def _save_summary(self, comparisons: List[AblationComparison]) -> None:
        """Save summary of all comparisons."""
        # Collect judge and semantic scores from MAS mode
        judge_overall_scores = []
        semantic_scores = []
        for c in comparisons:
            mas_result = c.results.get(AblationMode.MAS_FULL)
            if mas_result:
                if mas_result.judge_scores and 'overall_score' in mas_result.judge_scores:
                    judge_overall_scores.append(mas_result.judge_scores['overall_score'])
                if mas_result.semantic_score is not None:
                    semantic_scores.append(mas_result.semantic_score)

        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_test_cases': len(comparisons),
            'emergence_demonstrated_count': sum(
                1 for c in comparisons if c.emergence_demonstrated
            ),
            'average_mas_accuracy': sum(
                c.mas_accuracy for c in comparisons
            ) / len(comparisons) if comparisons else 0,
            'average_emergence_margin': sum(
                c.emergence_margin for c in comparisons
            ) / len(comparisons) if comparisons else 0,
            'average_judge_overall': sum(judge_overall_scores) / len(judge_overall_scores) if judge_overall_scores else None,
            'average_semantic_score': sum(semantic_scores) / len(semantic_scores) if semantic_scores else None,
            'test_cases': [c.model_dump() for c in comparisons]
        }

        filepath = self.results_dir / "ablation_summary.json"
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Saved summary: {filepath}")

    def print_comparison_table(self, comparisons: List[AblationComparison]) -> None:
        """Print ASCII comparison table."""
        print("\n" + "=" * 100)
        print("ABLATION COMPARISON RESULTS")
        print("=" * 100)

        for comp in comparisons:
            print(f"\nTest Case: {comp.test_case_name} ({comp.test_case_difficulty})")
            print("-" * 90)
            print(f"{'Mode':<20} {'Accuracy':<10} {'Confidence':<12} {'Keywords':<10} {'Judge':<10} {'Semantic':<10}")
            print("-" * 90)

            for mode, result in comp.results.items():
                judge_str = f"{result.judge_scores['overall_score']:.2f}" if result.judge_scores else "N/A"
                semantic_str = f"{result.semantic_score:.2f}" if result.semantic_score is not None else "N/A"
                print(
                    f"{mode:<20} {result.accuracy_score:<10.2%} "
                    f"{result.confidence:<12.2f} {result.keyword_matches}/{result.total_keywords:<6} "
                    f"{judge_str:<10} {semantic_str:<10}"
                )

            print("-" * 90)
            print(f"Best Single Agent: {comp.best_single_agent_accuracy:.2%}")
            print(f"MAS Full:          {comp.mas_accuracy:.2%}")
            print(f"Emergence Margin:  {comp.emergence_margin:+.2%}")
            print(f"Emergence Demo:    {'YES' if comp.emergence_demonstrated else 'NO'}")


async def main():
    """Test the ablation runner."""
    logger.info("=" * 60)
    logger.info("Testing Ablation Test Runner")
    logger.info("=" * 60)

    runner = AblationTestRunner()

    # Run single test case
    test_case = DEFAULT_TEST_SUITE.test_cases[0]  # Cascading thermal fault

    logger.info(f"\nRunning ablation for: {test_case.name}")
    logger.info("NOTE: This requires agent services to be running.")

    try:
        comparison = await runner.run_ablation(test_case)
        runner.print_comparison_table([comparison])

    except Exception as e:
        logger.error(f"Ablation test failed: {e}")
        logger.info("\nTo run ablation tests:")
        logger.info("1. Start agent services on ports 8001-8003")
        logger.info("2. Run: python -m src.evaluation.ablation_runner")

    logger.info("\n" + "=" * 60)
    logger.info("Ablation runner test complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
