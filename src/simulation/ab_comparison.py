"""
A/B Comparison Runner for Single-Agent vs Multi-Agent Evaluation

Purpose:
- Runs cross-domain scenarios in both baseline (single-agent) and multi-agent modes
- Collects metrics for thesis RQ2 evaluation
- Performs statistical comparison (paired t-test, effect size)
- Generates LaTeX tables for Results chapter

Usage:
    # Run comparison
    python -m src.simulation.ab_comparison --scenarios all

    # Generate report only (from existing results)
    python -m src.simulation.ab_comparison --report-only

Metrics Collected:
- MTTI (Mean Time to Innocence)
- Keyword accuracy
- Cross-domain resolution rate
- Delegation accuracy (multi-agent only)
- Communication overhead

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import os
import sys
import json
import time
import argparse
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from statistics import mean, stdev

import httpx

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.protocol.schema import (
    AgentCard, AgentRole, IntentType, Priority,
    ConsultRequest
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
MINISTER_URL = os.getenv("TELEKOM_MINISTER_URL", "http://localhost:8001")
SCENARIOS_DIR = project_root / "data" / "scenarios"
RESULTS_DIR = project_root / "results" / "ab_comparison"


@dataclass
class ScenarioResult:
    """Result from a single scenario execution."""
    scenario_id: str
    mode: str  # "baseline" or "multi_agent"
    mtti_seconds: float
    keyword_accuracy: float
    risk_match: bool
    sla_match: bool
    delegation_occurred: bool
    delegation_target: str
    cross_domain_resolution: float  # 0-1 based on domains covered
    response_success: bool
    timestamp: str
    raw_response: Optional[Dict] = None


class ABComparisonRunner:
    """
    Runs A/B comparison between single-agent baseline and multi-agent system.

    Ensures fair comparison:
    - Same LLM, temperature, retrieval k
    - Same scenarios and ground truth
    - Same evaluation metrics
    """

    def __init__(self, scenario_file: str = "cross_domain_evaluation.json"):
        """
        Initialize the comparison runner.

        Args:
            scenario_file: Name of scenario JSON file in data/scenarios/
        """
        self.scenario_file = scenario_file
        self.scenario_data: Optional[Dict[str, Any]] = None
        self.baseline_results: List[ScenarioResult] = []
        self.multi_agent_results: List[ScenarioResult] = []

    def load_scenario_data(self) -> Dict[str, Any]:
        """Load scenario data from JSON file."""
        scenario_path = SCENARIOS_DIR / self.scenario_file

        if not scenario_path.exists():
            raise FileNotFoundError(f"Scenario file not found: {scenario_path}")

        logger.info(f"Loading scenarios from {scenario_path}")

        with open(scenario_path, 'r') as f:
            self.scenario_data = json.load(f)

        logger.info(f"Loaded: {self.scenario_data.get('scenario_name')}")
        logger.info(f"Scenarios to test: {len(self.scenario_data.get('faults', []))}")

        return self.scenario_data

    def check_agent_health(self, mode: str) -> bool:
        """
        Check if agent is running and in correct mode.

        Args:
            mode: Expected mode ('baseline' or 'multi_agent')
        """
        try:
            response = httpx.get(f"{MINISTER_URL}/", timeout=5.0)
            if response.status_code != 200:
                return False

            data = response.json()
            agent_mode = "baseline" if data.get("baseline_mode", False) else "multi_agent"

            if agent_mode != mode:
                logger.warning(f"Agent is in {agent_mode} mode, expected {mode}")
                return False

            logger.info(f"Agent health check passed - mode: {mode}")
            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def send_query(
        self,
        query: str,
        location: str = "unknown",
        is_symptom: bool = True
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Send a query to the Minister and measure response time.

        Returns:
            Tuple of (response dict, mtti in seconds)
        """
        card = AgentCard(
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.TELEKOM_MINISTER,
            intent=IntentType.QUERY,
            priority=Priority.HIGH,
            payload={
                "query": query,
                "location": location,
                "is_symptom": is_symptom
            }
        )

        request = ConsultRequest(card=card)

        start_time = time.time()
        try:
            response = httpx.post(
                f"{MINISTER_URL}/consult",
                json=request.model_dump(),
                timeout=90.0  # Longer timeout for baseline with unified store
            )
            mtti = time.time() - start_time

            if response.status_code == 200:
                return response.json(), mtti
            else:
                logger.error(f"Request failed: {response.status_code}")
                return None, mtti

        except Exception as e:
            mtti = time.time() - start_time
            logger.error(f"Request failed: {e}")
            return None, mtti

    def evaluate_response(
        self,
        response: Optional[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        required_domains: List[str]
    ) -> Dict[str, Any]:
        """
        Evaluate response against ground truth.

        Args:
            response: Agent response
            ground_truth: Expected results
            required_domains: Domains needed for full resolution

        Returns:
            Evaluation metrics
        """
        metrics = {
            "keyword_accuracy": 0.0,
            "keyword_hits": 0,
            "keyword_total": 0,
            "risk_match": False,
            "sla_match": False,
            "delegation_occurred": False,
            "delegation_target": "none",
            "cross_domain_resolution": 0.0,
            "domains_covered": []
        }

        if not response:
            return metrics

        response_card = response.get('response_card', {})
        payload = response_card.get('payload', {})

        # Build response text for analysis
        response_text = " ".join([
            str(payload.get('answer', '')),
            str(payload.get('risk_level', '')),
            str(payload.get('violated_slas', '')),
            str(payload.get('recommended_actions', '')),
        ]).lower()

        # Check delegation
        delegation = payload.get('delegation', {})
        target = delegation.get('target_agent', 'self')
        skipped = delegation.get('skipped', False)

        metrics["delegation_target"] = target

        # Check specialist findings
        specialist = payload.get('specialist_findings')
        if specialist and not isinstance(specialist, dict):
            specialist = None

        if specialist:
            metrics["delegation_occurred"] = True
            spec_card = specialist.get('response_card', {})
            spec_payload = spec_card.get('payload', {})
            response_text += " " + " ".join([
                str(spec_payload.get('root_cause', '')),
                str(spec_payload.get('diagnosis', '')),
                str(spec_payload.get('answer', '')),
                str(spec_payload.get('corrective_actions', '')),
            ]).lower()

        # Keyword matching
        keywords = ground_truth.get('keywords', [])
        metrics["keyword_total"] = len(keywords)

        for keyword in keywords:
            if keyword.lower() in response_text:
                metrics["keyword_hits"] += 1

        if metrics["keyword_total"] > 0:
            metrics["keyword_accuracy"] = metrics["keyword_hits"] / metrics["keyword_total"]

        # Risk level matching
        predicted_risk = str(payload.get('risk_level', '')).lower()
        expected_risk = str(ground_truth.get('risk_level', '')).lower()
        metrics["risk_match"] = predicted_risk == expected_risk

        # SLA matching
        expected_slas = ground_truth.get('sla_violations', [])
        if expected_slas:
            sla_text = str(payload.get('violated_slas', '')).upper()
            metrics["sla_match"] = any(sla in sla_text for sla in expected_slas)

        # Cross-domain resolution scoring
        # Check which domains are reflected in the response
        domains_covered = []

        # Governance domain markers
        governance_markers = ['sla', 'policy', 'compliance', 'int-', 'governance']
        if any(m in response_text for m in governance_markers):
            domains_covered.append('governance')

        # Hardware domain markers
        hardware_markers = ['equipment', 'hardware', 'component', 'fm-', 'vs-', 'failure mode']
        if any(m in response_text for m in hardware_markers):
            domains_covered.append('hardware')

        # Operations domain markers
        ops_markers = ['station', 'session', 'charging', 'fault event', 'connector']
        if any(m in response_text for m in ops_markers):
            domains_covered.append('operations')

        metrics["domains_covered"] = domains_covered

        # Calculate cross-domain resolution score
        required_count = len(required_domains)
        covered_count = len([d for d in required_domains if d in domains_covered])
        metrics["cross_domain_resolution"] = covered_count / required_count if required_count > 0 else 0.0

        return metrics

    def run_scenarios(self, mode: str) -> List[ScenarioResult]:
        """
        Run all scenarios in the specified mode.

        Args:
            mode: 'baseline' or 'multi_agent'

        Returns:
            List of ScenarioResult objects
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Running scenarios in {mode.upper()} mode")
        logger.info(f"{'='*60}")

        if not self.scenario_data:
            self.load_scenario_data()

        # Check agent health
        if not self.check_agent_health(mode):
            raise RuntimeError(
                f"Agent not running in {mode} mode. "
                f"Set BASELINE_MODE={'true' if mode == 'baseline' else 'false'} and restart."
            )

        faults = self.scenario_data.get('faults', [])
        results = []

        for i, fault in enumerate(faults, 1):
            fault_id = fault.get('fault_id')
            query = fault.get('query')
            station_id = fault.get('station_id', 'unknown')
            ground_truth = fault.get('ground_truth', {})
            required_domains = fault.get('required_domains', ['governance', 'hardware', 'operations'])

            logger.info(f"\n--- Scenario {i}/{len(faults)}: {fault_id} ---")
            logger.info(f"Query: {query[:80]}...")

            # Send query
            response, mtti = self.send_query(
                query=query,
                location=station_id,
                is_symptom=True
            )

            # Evaluate
            evaluation = self.evaluate_response(response, ground_truth, required_domains)

            result = ScenarioResult(
                scenario_id=fault_id,
                mode=mode,
                mtti_seconds=mtti,
                keyword_accuracy=evaluation['keyword_accuracy'],
                risk_match=evaluation['risk_match'],
                sla_match=evaluation['sla_match'],
                delegation_occurred=evaluation['delegation_occurred'],
                delegation_target=evaluation['delegation_target'],
                cross_domain_resolution=evaluation['cross_domain_resolution'],
                response_success=response is not None,
                timestamp=datetime.now().isoformat(),
                raw_response=response
            )

            results.append(result)

            logger.info(f"MTTI: {mtti:.2f}s")
            logger.info(f"Keyword accuracy: {evaluation['keyword_accuracy']:.1%}")
            logger.info(f"Cross-domain resolution: {evaluation['cross_domain_resolution']:.1%}")
            logger.info(f"Domains covered: {evaluation['domains_covered']}")

        return results

    def run_baseline(self) -> List[ScenarioResult]:
        """Run all scenarios with baseline (single-agent) mode."""
        self.baseline_results = self.run_scenarios("baseline")
        return self.baseline_results

    def run_multi_agent(self) -> List[ScenarioResult]:
        """Run all scenarios with multi-agent mode."""
        self.multi_agent_results = self.run_scenarios("multi_agent")
        return self.multi_agent_results

    def compare_results(self) -> Dict[str, Any]:
        """
        Perform statistical comparison between baseline and multi-agent results.

        Returns:
            Comparison statistics including t-test results
        """
        if not self.baseline_results or not self.multi_agent_results:
            raise ValueError("Must run both baseline and multi-agent scenarios first")

        # Extract metrics for comparison
        baseline_mtti = [r.mtti_seconds for r in self.baseline_results]
        multi_agent_mtti = [r.mtti_seconds for r in self.multi_agent_results]

        baseline_accuracy = [r.keyword_accuracy for r in self.baseline_results]
        multi_agent_accuracy = [r.keyword_accuracy for r in self.multi_agent_results]

        baseline_cross_domain = [r.cross_domain_resolution for r in self.baseline_results]
        multi_agent_cross_domain = [r.cross_domain_resolution for r in self.multi_agent_results]

        # Calculate statistics
        comparison = {
            "scenario_count": len(self.baseline_results),
            "mtti": {
                "baseline_mean": mean(baseline_mtti),
                "baseline_stdev": stdev(baseline_mtti) if len(baseline_mtti) > 1 else 0,
                "multi_agent_mean": mean(multi_agent_mtti),
                "multi_agent_stdev": stdev(multi_agent_mtti) if len(multi_agent_mtti) > 1 else 0,
                "difference": mean(multi_agent_mtti) - mean(baseline_mtti),
                "overhead_percent": ((mean(multi_agent_mtti) - mean(baseline_mtti)) / mean(baseline_mtti)) * 100 if mean(baseline_mtti) > 0 else 0
            },
            "keyword_accuracy": {
                "baseline_mean": mean(baseline_accuracy),
                "multi_agent_mean": mean(multi_agent_accuracy),
                "difference": mean(multi_agent_accuracy) - mean(baseline_accuracy)
            },
            "cross_domain_resolution": {
                "baseline_mean": mean(baseline_cross_domain),
                "multi_agent_mean": mean(multi_agent_cross_domain),
                "difference": mean(multi_agent_cross_domain) - mean(baseline_cross_domain)
            },
            "delegation": {
                "multi_agent_delegation_rate": sum(1 for r in self.multi_agent_results if r.delegation_occurred) / len(self.multi_agent_results)
            }
        }

        # Statistical tests
        try:
            from scipy import stats

            # Paired t-test for MTTI
            t_stat, p_value = stats.ttest_rel(baseline_mtti, multi_agent_mtti)
            comparison["mtti"]["t_statistic"] = t_stat
            comparison["mtti"]["p_value"] = p_value
            comparison["mtti"]["significant"] = p_value < 0.05

            # Effect size (Cohen's d)
            pooled_std = ((stdev(baseline_mtti)**2 + stdev(multi_agent_mtti)**2) / 2) ** 0.5
            cohens_d = (mean(multi_agent_mtti) - mean(baseline_mtti)) / pooled_std if pooled_std > 0 else 0
            comparison["mtti"]["cohens_d"] = cohens_d

            # Paired t-test for accuracy
            t_stat_acc, p_value_acc = stats.ttest_rel(baseline_accuracy, multi_agent_accuracy)
            comparison["keyword_accuracy"]["t_statistic"] = t_stat_acc
            comparison["keyword_accuracy"]["p_value"] = p_value_acc
            comparison["keyword_accuracy"]["significant"] = p_value_acc < 0.05

        except ImportError:
            logger.warning("scipy not available, skipping statistical tests")

        # Per-scenario comparison
        per_scenario = []
        for baseline, multi in zip(self.baseline_results, self.multi_agent_results):
            per_scenario.append({
                "scenario_id": baseline.scenario_id,
                "baseline_mtti": baseline.mtti_seconds,
                "multi_agent_mtti": multi.mtti_seconds,
                "mtti_difference": multi.mtti_seconds - baseline.mtti_seconds,
                "baseline_accuracy": baseline.keyword_accuracy,
                "multi_agent_accuracy": multi.keyword_accuracy,
                "accuracy_difference": multi.keyword_accuracy - baseline.keyword_accuracy,
                "baseline_cross_domain": baseline.cross_domain_resolution,
                "multi_agent_cross_domain": multi.cross_domain_resolution,
                "multi_agent_wins_accuracy": multi.keyword_accuracy > baseline.keyword_accuracy,
                "multi_agent_wins_cross_domain": multi.cross_domain_resolution > baseline.cross_domain_resolution
            })

        comparison["per_scenario"] = per_scenario

        # Summary: Count where each approach wins
        comparison["summary"] = {
            "multi_agent_accuracy_wins": sum(1 for s in per_scenario if s["multi_agent_wins_accuracy"]),
            "baseline_accuracy_wins": sum(1 for s in per_scenario if not s["multi_agent_wins_accuracy"]),
            "multi_agent_cross_domain_wins": sum(1 for s in per_scenario if s["multi_agent_wins_cross_domain"]),
            "baseline_cross_domain_wins": sum(1 for s in per_scenario if not s["multi_agent_wins_cross_domain"]),
            "ties": sum(1 for s in per_scenario if s["accuracy_difference"] == 0)
        }

        return comparison

    def generate_latex_tables(self, comparison: Dict[str, Any]) -> str:
        """
        Generate LaTeX tables for thesis Results chapter.

        Args:
            comparison: Comparison statistics from compare_results()

        Returns:
            LaTeX formatted tables as string
        """
        latex = []

        # Table 1: Aggregate Metrics Comparison
        latex.append(r"""
\begin{table}[htbp]
\centering
\caption{Aggregate Performance Comparison: Single-Agent Baseline vs Multi-Agent System}
\label{tab:ab-comparison}
\begin{tabular}{lccc}
\toprule
\textbf{Metric} & \textbf{Baseline} & \textbf{Multi-Agent} & \textbf{Difference} \\
\midrule""")

        mtti = comparison["mtti"]
        acc = comparison["keyword_accuracy"]
        cross = comparison["cross_domain_resolution"]

        latex.append(f"MTTI (seconds) & {mtti['baseline_mean']:.2f} $\\pm$ {mtti['baseline_stdev']:.2f} & {mtti['multi_agent_mean']:.2f} $\\pm$ {mtti['multi_agent_stdev']:.2f} & {mtti['difference']:+.2f} \\\\")
        latex.append(f"Keyword Accuracy & {acc['baseline_mean']:.1%} & {acc['multi_agent_mean']:.1%} & {acc['difference']:+.1%} \\\\")
        latex.append(f"Cross-Domain Resolution & {cross['baseline_mean']:.1%} & {cross['multi_agent_mean']:.1%} & {cross['difference']:+.1%} \\\\")

        latex.append(r"""\bottomrule
\end{tabular}
\end{table}
""")

        # Table 2: Statistical Significance
        if "t_statistic" in mtti:
            latex.append(r"""
\begin{table}[htbp]
\centering
\caption{Statistical Analysis of MTTI Difference}
\label{tab:statistical-analysis}
\begin{tabular}{lc}
\toprule
\textbf{Statistic} & \textbf{Value} \\
\midrule""")

            latex.append(f"t-statistic & {mtti['t_statistic']:.3f} \\\\")
            latex.append(f"p-value & {mtti['p_value']:.4f} \\\\")
            latex.append(f"Cohen's d (effect size) & {mtti['cohens_d']:.3f} \\\\")
            sig = "Yes" if mtti['significant'] else "No"
            latex.append(f"Significant ($p < 0.05$) & {sig} \\\\")

            latex.append(r"""\bottomrule
\end{tabular}
\end{table}
""")

        # Table 3: Per-Scenario Breakdown
        latex.append(r"""
\begin{table}[htbp]
\centering
\caption{Per-Scenario Performance Comparison}
\label{tab:per-scenario}
\begin{tabular}{lcccccc}
\toprule
\textbf{Scenario} & \multicolumn{2}{c}{\textbf{MTTI (s)}} & \multicolumn{2}{c}{\textbf{Accuracy}} & \multicolumn{2}{c}{\textbf{Cross-Domain}} \\
\cmidrule(lr){2-3} \cmidrule(lr){4-5} \cmidrule(lr){6-7}
 & Base & MAS & Base & MAS & Base & MAS \\
\midrule""")

        for s in comparison["per_scenario"]:
            latex.append(
                f"{s['scenario_id']} & {s['baseline_mtti']:.1f} & {s['multi_agent_mtti']:.1f} & "
                f"{s['baseline_accuracy']:.0%} & {s['multi_agent_accuracy']:.0%} & "
                f"{s['baseline_cross_domain']:.0%} & {s['multi_agent_cross_domain']:.0%} \\\\"
            )

        latex.append(r"""\bottomrule
\end{tabular}
\end{table}
""")

        return "\n".join(latex)

    def save_results(self, comparison: Optional[Dict[str, Any]] = None, output_dir: Optional[Path] = None) -> Dict[str, Path]:
        """
        Save all available results to files. Handles partial results (baseline only or multi-agent only).
        """
        if output_dir is None:
            output_dir = RESULTS_DIR

        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_paths = {}

        # 1. Save baseline results if they exist
        if self.baseline_results:
            baseline_path = output_dir / f"baseline_results_{timestamp}.json"
            with open(baseline_path, 'w') as f:
                json.dump([asdict(r) for r in self.baseline_results], f, indent=2, default=str)
            logger.info(f"Baseline results saved to {baseline_path}")
            saved_paths["baseline"] = baseline_path

        # 2. Save multi-agent results if they exist
        if self.multi_agent_results:
            multi_path = output_dir / f"multi_agent_results_{timestamp}.json"
            with open(multi_path, 'w') as f:
                json.dump([asdict(r) for r in self.multi_agent_results], f, indent=2, default=str)
            logger.info(f"Multi-agent results saved to {multi_path}")
            saved_paths["multi_agent"] = multi_path

        # 3. Save comparison and LaTeX ONLY if comparison data is provided
        if comparison:
            comparison_path = output_dir / f"comparison_{timestamp}.json"
            with open(comparison_path, 'w') as f:
                json.dump(comparison, f, indent=2)
            logger.info(f"Comparison saved to {comparison_path}")
            saved_paths["comparison"] = comparison_path

            # Save LaTeX tables
            latex_tables = self.generate_latex_tables(comparison)
            latex_path = output_dir / f"latex_tables_{timestamp}.tex"
            with open(latex_path, 'w') as f:
                f.write(latex_tables)
            logger.info(f"LaTeX tables saved to {latex_path}")
            saved_paths["latex"] = latex_path

        return saved_paths

    def print_summary(self, comparison: Dict[str, Any]):
        """Print a summary of the comparison results."""
        print("\n" + "=" * 70)
        print("A/B COMPARISON SUMMARY")
        print("=" * 70)

        mtti = comparison["mtti"]
        acc = comparison["keyword_accuracy"]
        cross = comparison["cross_domain_resolution"]
        summary = comparison["summary"]

        print(f"\n{'Metric':<30} {'Baseline':>15} {'Multi-Agent':>15} {'Diff':>10}")
        print("-" * 70)
        print(f"{'MTTI (seconds)':<30} {mtti['baseline_mean']:>15.2f} {mtti['multi_agent_mean']:>15.2f} {mtti['difference']:>+10.2f}")
        print(f"{'Keyword Accuracy':<30} {acc['baseline_mean']:>14.1%} {acc['multi_agent_mean']:>14.1%} {acc['difference']:>+9.1%}")
        print(f"{'Cross-Domain Resolution':<30} {cross['baseline_mean']:>14.1%} {cross['multi_agent_mean']:>14.1%} {cross['difference']:>+9.1%}")

        print(f"\n{'Statistical Significance (MTTI)':}")
        if "t_statistic" in mtti:
            print(f"  t-statistic: {mtti['t_statistic']:.3f}")
            print(f"  p-value: {mtti['p_value']:.4f}")
            print(f"  Effect size (Cohen's d): {mtti['cohens_d']:.3f}")
            print(f"  Significant: {'Yes' if mtti['significant'] else 'No'}")

        print(f"\n{'Win/Loss Summary':}")
        print(f"  Multi-agent wins on accuracy: {summary['multi_agent_accuracy_wins']}/{comparison['scenario_count']}")
        print(f"  Multi-agent wins on cross-domain: {summary['multi_agent_cross_domain_wins']}/{comparison['scenario_count']}")

        # Coordination overhead analysis
        if mtti['overhead_percent'] > 0:
            print(f"\n{'Coordination Overhead':}")
            print(f"  Multi-agent is {mtti['overhead_percent']:.1f}% slower (coordination cost)")
        else:
            print(f"\n{'Multi-Agent Efficiency':}")
            print(f"  Multi-agent is {-mtti['overhead_percent']:.1f}% faster")

        print("\n" + "=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="A/B Comparison: Single-Agent vs Multi-Agent")
    parser.add_argument("--scenarios", default="cross_domain_evaluation.json", help="Scenario file name")
    parser.add_argument("--output", default=None, help="Output directory")
    parser.add_argument("--report-only", action="store_true", help="Generate report from existing results")
    parser.add_argument("--mode", choices=["baseline", "multi_agent", "both"], default="both", help="Which mode to run")

    args = parser.parse_args()

    print("=" * 70)
    print("A/B COMPARISON: Single-Agent Baseline vs Multi-Agent System")
    print("Thesis RQ2 Evaluation Framework")
    print("=" * 70)
    print()

    runner = ABComparisonRunner(scenario_file=args.scenarios)

    try:
        runner.load_scenario_data()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return

    # --- PHASE 1: BASELINE ---
    if args.mode in ["baseline", "both"]:
        print("\n" + "=" * 50)
        print("PHASE 1: Running Baseline (Single-Agent) Mode")
        print("=" * 50)
        print("NOTE: Ensure agent is started with BASELINE_MODE=true")
        print()

        input("Press Enter when baseline agent is ready...")
        runner.run_baseline()
        
        # FIX: Save immediately after running
        runner.save_results(comparison=None)

    # --- PHASE 2: MULTI-AGENT ---
    if args.mode in ["multi_agent", "both"]:
        print("\n" + "=" * 50)
        print("PHASE 2: Running Multi-Agent Mode")
        print("=" * 50)
        print("NOTE: Ensure agent is started with BASELINE_MODE=false (default)")
        print()

        input("Press Enter when multi-agent system is ready...")
        runner.run_multi_agent()
        
        # FIX: Save immediately after running
        runner.save_results(comparison=None)

    # --- PHASE 3: COMPARISON (Only if both are in memory) ---
    if runner.baseline_results and runner.multi_agent_results:
        print("\n" + "=" * 50)
        print("PHASE 3: Analyzing Results")
        print("=" * 50)

        comparison = runner.compare_results()
        runner.print_summary(comparison)

        output_dir = Path(args.output) if args.output else None
        paths = runner.save_results(comparison, output_dir)

        print(f"\nFinal Comparison saved to:")
        for name, path in paths.items():
            print(f"  {name}: {path}")
            
    else:
        print("\n[INFO] Partial run complete. To compare, run the other mode and use --report-only (or load JSONs manually).")


if __name__ == "__main__":
    main()
