"""
Evaluation Service - in-memory state manager for evaluation runs.

Bridges run_evaluation.py logic to FastAPI async endpoints.
Maintains run state and drives background evaluation tasks via asyncio.create_task.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

RESULTS_DIR = Path("results/ablation")


@dataclass
class EvalRunState:
    run_id: str
    status: str  # "running" | "completed" | "failed"
    started_at: str
    total_evaluations: int
    completed_evaluations: int = 0
    current_test_case: str = ""
    current_mode: str = ""
    comparisons: list = field(default_factory=list)
    thesis_summary: Optional[dict] = None
    error: Optional[str] = None


class EvalService:
    def __init__(self):
        self.runs: dict[str, EvalRunState] = {}

    async def start_run(
        self,
        test_cases: Optional[list[str]],
        no_resume: bool,
    ) -> tuple[str, int]:
        """Start a background evaluation run. Returns (run_id, total_evaluations)."""
        from src.evaluation.emergence_tests import DEFAULT_TEST_SUITE, EmergenceTestSuite

        suite = DEFAULT_TEST_SUITE
        if test_cases:
            matching = [tc for tc in suite.test_cases if tc.name in test_cases]
            suite = EmergenceTestSuite(
                name=suite.name,
                description=suite.description,
                test_cases=matching,
            )

        total = len(suite.test_cases) * 5  # 5 modes per test case
        run_id = str(uuid.uuid4())[:8]
        state = EvalRunState(
            run_id=run_id,
            status="running",
            started_at=datetime.now(timezone.utc).isoformat(),
            total_evaluations=total,
        )
        self.runs[run_id] = state

        asyncio.create_task(self._run_background(run_id, suite, no_resume))
        return run_id, total

    async def _run_background(self, run_id: str, suite, no_resume: bool) -> None:
        from src.evaluation.ablation_runner import AblationTestRunner
        from src.evaluation.run_evaluation import generate_thesis_summary, load_existing_result

        state = self.runs[run_id]
        results_path = RESULTS_DIR
        results_path.mkdir(parents=True, exist_ok=True)

        runner = AblationTestRunner(log_dir=str(results_path))
        comparisons = []
        total_cases = len(suite.test_cases)

        try:
            for idx, test_case in enumerate(suite.test_cases, 1):
                state.current_test_case = test_case.name
                state.current_mode = "starting"

                # Resume: skip if already complete
                if not no_resume:
                    existing = load_existing_result(results_path, test_case.name)
                    if existing:
                        comparisons.append(existing)
                        state.completed_evaluations += 5
                        state.comparisons = [c.model_dump() for c in comparisons]
                        logger.info(f"Skipped (resume): {test_case.name}")
                        continue

                state.current_mode = "running"
                try:
                    comparison = await runner.run_ablation(test_case)
                    comparisons.append(comparison)
                    runner._save_comparison(comparison)
                except Exception as e:
                    logger.error(f"FAILED {test_case.name}: {e}")

                state.completed_evaluations += 5
                state.comparisons = [c.model_dump() for c in comparisons]

                # Rate-limit delay between test cases
                if idx < total_cases:
                    await asyncio.sleep(2)

            # Generate thesis summary
            if comparisons:
                summary = generate_thesis_summary(comparisons, results_path)
                state.thesis_summary = summary

            state.comparisons = [c.model_dump() for c in comparisons]
            state.status = "completed"
            state.current_mode = ""
            logger.info(f"Eval run {run_id} completed: {len(comparisons)} test cases")

        except Exception as e:
            logger.error(f"Eval run {run_id} failed: {e}", exc_info=True)
            state.status = "failed"
            state.error = str(e)

    def get_status(self, run_id: str) -> Optional[EvalRunState]:
        return self.runs.get(run_id)

    def get_all_results(self) -> list[dict]:
        """Load all past ablation results from disk."""
        results = []
        if not RESULTS_DIR.exists():
            return results
        for filepath in sorted(RESULTS_DIR.glob("*_ablation.json")):
            try:
                with open(filepath) as f:
                    results.append(json.load(f))
            except Exception as e:
                logger.warning(f"Could not load {filepath}: {e}")
        return results
