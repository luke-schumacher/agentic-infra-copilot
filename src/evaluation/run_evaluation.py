"""
Evaluation Orchestrator - Full Thesis Benchmarking Suite

Runs the 5-mode ablation study across all 12 emergence test cases (60 total evaluations)
to answer RQ1-RQ3. Includes pre-flight health checks, resume support, and thesis-formatted
summary output.

Usage:
    python -m src.evaluation.run_evaluation                    # Full suite
    python -m src.evaluation.run_evaluation --dry-run          # Health check only
    python -m src.evaluation.run_evaluation --test-case NAME   # Single test case
    python -m src.evaluation.run_evaluation --no-resume        # Skip resume, rerun all

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import httpx

from src.evaluation.ablation_runner import (
    AblationComparison,
    AblationMode,
    AblationTestRunner,
)
from src.evaluation.emergence_tests import (
    DEFAULT_TEST_SUITE,
    Difficulty,
    EmergenceTestSuite,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Agent endpoints
AGENTS = {
    "governance_agent": "http://localhost:8001",
    "hardware_agent": "http://localhost:8002",
    "telemetry_agent": "http://localhost:8003",
}

DELAY_BETWEEN_CASES_S = 45


# ---------------------------------------------------------------------------
# Pre-flight health check
# ---------------------------------------------------------------------------

async def check_agent_health(name: str, url: str) -> Dict:
    """Hit /health on a single agent. Returns parsed JSON or error dict."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{url}/health")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"status": "unreachable", "error": str(e), "document_count": 0}


async def probe_agent_consult(name: str, url: str) -> bool:
    """
    Send a minimal /consult probe to confirm the agent can actually process
    requests end-to-end (DSPy + vector store), not just pass the health check.

    Returns True if the agent responds with a 200 (even empty findings are OK —
    we only care that it doesn't time out or error).
    """
    from src.protocol.schema import AgentCard, AgentRole, IntentType, Priority
    card = AgentCard(
        sender=AgentRole.ORCHESTRATOR,
        recipient=AgentRole(name),
        intent=IntentType.DIAGNOSE,
        priority=Priority.LOW,
        payload={
            "query": "preflight probe: MRI system status check",
            "context": {"accumulated_context": "", "is_consultation": False, "expertise_needed": ""},
        },
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{url}/consult",
                json={"card": card.model_dump(), "await_response": True},
            )
            return resp.status_code == 200
    except Exception:
        return False


async def preflight_check() -> bool:
    """
    Check all agents are healthy with documents indexed AND can process a
    real /consult request. Returns True only if all three pass both checks.
    """
    print("\n" + "=" * 60)
    print("PRE-FLIGHT HEALTH CHECK")
    print("=" * 60)

    all_ok = True
    for name, url in AGENTS.items():
        health = await check_agent_health(name, url)
        status = health.get("status", "unknown")
        doc_count = health.get("document_count", 0)
        vs_ready = health.get("vector_store_ready", False)
        dspy_ready = health.get("dspy_ready", False)

        # Step 1: health endpoint
        health_ok = status in ("healthy", "degraded") and doc_count > 0
        icon = "[OK]" if health_ok else "[FAIL]"
        print(
            f"  {icon} {name:20s}  status={status:10s}  "
            f"docs={doc_count}  vs={vs_ready}  dspy={dspy_ready}  "
            f"url={url}"
        )

        if not health_ok:
            all_ok = False
            continue

        # Step 2: live consult probe — confirms DSPy + vector store end-to-end
        print(f"       probing /consult ... ", end="", flush=True)
        consult_ok = await probe_agent_consult(name, url)
        if consult_ok:
            print("OK")
        else:
            print("FAIL  ← agent not responding to queries")
            all_ok = False

    print("=" * 60)
    if all_ok:
        print("All agents healthy and responding to queries.")
    else:
        print("ABORT: One or more agents failed health or consult probe.")
        print("       Start all 3 agents (ports 8001-8003) and retry.")
    print()
    return all_ok


# ---------------------------------------------------------------------------
# Resume support
# ---------------------------------------------------------------------------

def load_existing_result(results_dir: Path, test_case_name: str) -> Optional[AblationComparison]:
    """Load an existing ablation result if present and valid."""
    filepath = results_dir / f"{test_case_name}_ablation.json"
    if not filepath.exists():
        return None
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        comp = AblationComparison(**data)
        # Valid only if all 5 modes are present
        if len(comp.results) == len(AblationMode.ALL_MODES):
            return comp
        logger.info(f"Incomplete result for {test_case_name} ({len(comp.results)}/5 modes), will re-run")
        return None
    except Exception as e:
        logger.warning(f"Could not load existing result for {test_case_name}: {e}")
        return None


# ---------------------------------------------------------------------------
# Thesis summary generation
# ---------------------------------------------------------------------------

def generate_thesis_summary(
    comparisons: List[AblationComparison],
    results_dir: Path,
) -> Dict:
    """
    Generate enhanced thesis summary with per-mode averages, per-difficulty
    breakdowns, emergence analysis, latency comparison, and response type
    distribution.
    """
    if not comparisons:
        return {}

    # Per-mode averages
    mode_accuracies: Dict[str, List[float]] = {m: [] for m in AblationMode.ALL_MODES}
    mode_latencies: Dict[str, List[float]] = {m: [] for m in AblationMode.ALL_MODES}
    mode_judge_scores: Dict[str, List[float]] = {m: [] for m in AblationMode.ALL_MODES}
    mode_semantic_scores: Dict[str, List[float]] = {m: [] for m in AblationMode.ALL_MODES}

    for comp in comparisons:
        for mode, result in comp.results.items():
            mode_accuracies[mode].append(result.accuracy_score)
            mode_latencies[mode].append(result.latency_ms)
            if result.judge_scores and "overall_score" in result.judge_scores:
                mode_judge_scores[mode].append(result.judge_scores["overall_score"])
            if result.semantic_score is not None:
                mode_semantic_scores[mode].append(result.semantic_score)

    def _avg(lst):
        return sum(lst) / len(lst) if lst else None

    per_mode = {}
    for mode in AblationMode.ALL_MODES:
        per_mode[mode] = {
            "avg_accuracy": _avg(mode_accuracies[mode]),
            "avg_latency_ms": _avg(mode_latencies[mode]),
            "avg_judge_overall": _avg(mode_judge_scores[mode]),
            "avg_semantic_score": _avg(mode_semantic_scores[mode]),
            "n_evaluations": len(mode_accuracies[mode]),
        }

    # Per-difficulty breakdown
    per_difficulty = {}
    for diff in Difficulty:
        cases = [c for c in comparisons if c.test_case_difficulty == diff.value]
        if not cases:
            continue
        per_difficulty[diff.value] = {
            "count": len(cases),
            "avg_mas_accuracy": _avg([c.mas_accuracy for c in cases]),
            "avg_best_single": _avg([c.best_single_agent_accuracy for c in cases]),
            "avg_emergence_margin": _avg([c.emergence_margin for c in cases]),
            "emergence_demonstrated": sum(1 for c in cases if c.emergence_demonstrated),
        }

    # Emergence analysis
    emergence_cases = [c for c in comparisons if c.emergence_demonstrated]
    emergence_list = []
    for c in emergence_cases:
        mas = c.results.get(AblationMode.MAS_FULL)
        emergence_list.append({
            "test_case": c.test_case_name,
            "difficulty": c.test_case_difficulty,
            "margin": c.emergence_margin,
            "mas_accuracy": c.mas_accuracy,
            "cross_domain_refs": mas.cross_domain_refs if mas else 0,
        })

    # Latency comparison (MAS vs single_all_data)
    latency_comparison = []
    for comp in comparisons:
        mas = comp.results.get(AblationMode.MAS_FULL)
        single = comp.results.get(AblationMode.SINGLE_ALL_DATA)
        if mas and single:
            latency_comparison.append({
                "test_case": comp.test_case_name,
                "mas_latency_ms": mas.latency_ms,
                "single_all_latency_ms": single.latency_ms,
                "overhead_ms": mas.latency_ms - single.latency_ms,
            })

    # Response type distribution (from MAS mode)
    agents_consulted_counts: Dict[str, int] = {}
    total_rounds = []
    for comp in comparisons:
        mas = comp.results.get(AblationMode.MAS_FULL)
        if mas:
            total_rounds.append(mas.rounds_used)
            for agent in mas.agents_consulted:
                agents_consulted_counts[agent] = agents_consulted_counts.get(agent, 0) + 1

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_test_cases": len(comparisons),
        "total_evaluations": len(comparisons) * len(AblationMode.ALL_MODES),
        "per_mode_averages": per_mode,
        "per_difficulty": per_difficulty,
        "emergence_analysis": {
            "total_demonstrated": len(emergence_cases),
            "total_tested": len(comparisons),
            "rate": len(emergence_cases) / len(comparisons) if comparisons else 0,
            "cases": emergence_list,
        },
        "latency_comparison": latency_comparison,
        "mas_response_distribution": {
            "agents_consulted_frequency": agents_consulted_counts,
            "avg_rounds_used": _avg(total_rounds),
        },
    }

    filepath = results_dir / "thesis_summary.json"
    with open(filepath, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"Saved thesis summary: {filepath}")

    return summary


def print_thesis_summary(summary: Dict) -> None:
    """Print human-readable thesis summary to stdout."""
    if not summary:
        print("No summary data.")
        return

    print("\n" + "=" * 70)
    print("THESIS EVALUATION SUMMARY")
    print("=" * 70)
    print(f"Total test cases: {summary['total_test_cases']}")
    print(f"Total evaluations: {summary['total_evaluations']}")

    # Per-mode table
    print(f"\n{'Mode':<20} {'Accuracy':>10} {'Latency(ms)':>12} {'Judge':>10} {'Semantic':>10}")
    print("-" * 62)
    for mode, data in summary.get("per_mode_averages", {}).items():
        acc = f"{data['avg_accuracy']:.2%}" if data["avg_accuracy"] is not None else "N/A"
        lat = f"{data['avg_latency_ms']:.0f}" if data["avg_latency_ms"] is not None else "N/A"
        jdg = f"{data['avg_judge_overall']:.2f}" if data["avg_judge_overall"] is not None else "N/A"
        sem = f"{data['avg_semantic_score']:.2f}" if data["avg_semantic_score"] is not None else "N/A"
        print(f"{mode:<20} {acc:>10} {lat:>12} {jdg:>10} {sem:>10}")

    # Per-difficulty
    print(f"\n{'Difficulty':<12} {'Cases':>6} {'MAS Acc':>10} {'Best Single':>12} {'Margin':>10} {'Emergence':>10}")
    print("-" * 60)
    for diff, data in summary.get("per_difficulty", {}).items():
        print(
            f"{diff:<12} {data['count']:>6} {data['avg_mas_accuracy']:>10.2%} "
            f"{data['avg_best_single']:>12.2%} {data['avg_emergence_margin']:>+10.2%} "
            f"{data['emergence_demonstrated']:>10d}"
        )

    # Emergence
    ea = summary.get("emergence_analysis", {})
    print(f"\nEmergence: {ea.get('total_demonstrated', 0)}/{ea.get('total_tested', 0)} "
          f"({ea.get('rate', 0):.0%})")
    for case in ea.get("cases", []):
        print(f"  + {case['test_case']} ({case['difficulty']}): margin={case['margin']:+.2%}")

    print("=" * 70)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

async def run_evaluation(
    test_case_name: Optional[str] = None,
    dry_run: bool = False,
    resume: bool = True,
    results_dir: str = "results/ablation",
) -> None:
    """Run the full evaluation suite."""
    results_path = Path(results_dir)
    results_path.mkdir(parents=True, exist_ok=True)

    # Pre-flight
    healthy = await preflight_check()
    if dry_run:
        print("Dry run complete. Exiting.")
        return
    if not healthy:
        print("Cannot proceed with unhealthy agents. Start all 3 agents first.")
        sys.exit(1)

    suite: EmergenceTestSuite = DEFAULT_TEST_SUITE

    # Filter to single test case if requested
    if test_case_name:
        matching = [tc for tc in suite.test_cases if tc.name == test_case_name]
        if not matching:
            available = [tc.name for tc in suite.test_cases]
            print(f"Unknown test case: {test_case_name}")
            print(f"Available: {', '.join(available)}")
            sys.exit(1)
        suite = EmergenceTestSuite(
            name=suite.name,
            description=suite.description,
            test_cases=matching,
        )

    total = len(suite.test_cases)
    print(f"\nRunning {total} test case(s) x 5 modes = {total * 5} evaluations")
    print()

    runner = AblationTestRunner(log_dir=results_dir)
    comparisons: List[AblationComparison] = []

    for idx, test_case in enumerate(suite.test_cases, 1):
        # Resume: check for existing result
        if resume:
            existing = load_existing_result(results_path, test_case.name)
            if existing:
                print(f"[{idx}/{total}] SKIP (resume) {test_case.name} — already complete")
                comparisons.append(existing)
                continue

        print(f"[{idx}/{total}] Running: {test_case.name} ({test_case.difficulty.value})")
        start = time.time()

        try:
            comparison = await runner.run_ablation(test_case)
            comparisons.append(comparison)

            # Save individual result for resume support
            runner._save_comparison(comparison)

            elapsed = time.time() - start
            em = "YES" if comparison.emergence_demonstrated else "no"
            print(
                f"         Done in {elapsed:.1f}s — MAS={comparison.mas_accuracy:.0%} "
                f"best_single={comparison.best_single_agent_accuracy:.0%} "
                f"margin={comparison.emergence_margin:+.0%} emergence={em}"
            )
        except Exception as e:
            logger.error(f"FAILED {test_case.name}: {e}")
            print(f"         FAILED: {e}")

        # Rate-limit delay between test cases
        if idx < total:
            await asyncio.sleep(DELAY_BETWEEN_CASES_S)

    # Generate thesis summary
    if comparisons:
        runner.print_comparison_table(comparisons)
        summary = generate_thesis_summary(comparisons, results_path)
        print_thesis_summary(summary)
    else:
        print("No completed evaluations to summarize.")


def main():
    parser = argparse.ArgumentParser(
        description="Run the full thesis evaluation & benchmarking suite"
    )
    parser.add_argument(
        "--test-case",
        type=str,
        default=None,
        help="Run a single test case by name (e.g., cascading_thermal_fault)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only run pre-flight health check, do not evaluate",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore existing results and rerun everything",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="results/ablation",
        help="Directory for result files (default: results/ablation)",
    )
    args = parser.parse_args()

    asyncio.run(
        run_evaluation(
            test_case_name=args.test_case,
            dry_run=args.dry_run,
            resume=not args.no_resume,
            results_dir=args.results_dir,
        )
    )


if __name__ == "__main__":
    main()
