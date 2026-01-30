"""
Generate Comparison Report from Existing Results

Loads baseline and multi-agent results from JSON files and generates:
- Comparison statistics (including CooperBench metrics)
- LaTeX tables for thesis
- Visualization plots

Usage:
    python -m src.simulation.generate_comparison
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from statistics import mean, stdev
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.evaluation.metrics import (
    calculate_communication_overhead,
    information_integration_score,
    cooperation_effectiveness,
    CommunicationOverhead,
    IntegrationScore
)

RESULTS_DIR = project_root / "results" / "ab_comparison"


@dataclass
class ScenarioResult:
    """Result from a single scenario execution."""
    scenario_id: str
    mode: str
    mtti_seconds: float
    keyword_accuracy: float
    risk_match: bool
    sla_match: bool
    delegation_occurred: bool
    delegation_target: str
    cross_domain_resolution: float
    response_success: bool
    timestamp: str
    raw_response: Dict = None


def load_results(filepath: Path) -> List[ScenarioResult]:
    """Load results from JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    results = []
    for item in data:
        results.append(ScenarioResult(
            scenario_id=item['scenario_id'],
            mode=item['mode'],
            mtti_seconds=item['mtti_seconds'],
            keyword_accuracy=item['keyword_accuracy'],
            risk_match=item['risk_match'],
            sla_match=item['sla_match'],
            delegation_occurred=item['delegation_occurred'],
            delegation_target=item['delegation_target'],
            cross_domain_resolution=item['cross_domain_resolution'],
            response_success=item['response_success'],
            timestamp=item['timestamp'],
            raw_response=item.get('raw_response')
        ))

    return results


def compute_cooperbench_metrics(
    baseline_results: List[ScenarioResult],
    multi_agent_results: List[ScenarioResult]
) -> Dict[str, Any]:
    """
    Compute CooperBench-inspired metrics.

    Returns metrics measuring cooperation effectiveness, communication overhead,
    and information integration quality.
    """
    # 1. Cooperation Effectiveness (from metrics.py)
    baseline_dicts = [
        {'keyword_accuracy': r.keyword_accuracy, 'mtti_seconds': r.mtti_seconds}
        for r in baseline_results
    ]
    multi_agent_dicts = [
        {'keyword_accuracy': r.keyword_accuracy, 'mtti_seconds': r.mtti_seconds}
        for r in multi_agent_results
    ]

    coop_effectiveness = cooperation_effectiveness(baseline_dicts, multi_agent_dicts)

    # 2. Communication Overhead (per scenario)
    overhead_metrics = []
    for result in multi_agent_results:
        if result.raw_response:
            overhead = calculate_communication_overhead(
                result.raw_response,
                result.mtti_seconds * 1000  # Convert to ms
            )
            overhead_metrics.append({
                'scenario_id': result.scenario_id,
                'delegation_count': overhead.delegation_count,
                'total_delegation_time_ms': overhead.total_delegation_time_ms,
                'delegation_success_rate': overhead.delegation_success_rate,
                'overhead_ratio': overhead.overhead_ratio
            })

    # Aggregate overhead stats
    if overhead_metrics:
        avg_overhead_ratio = mean(o['overhead_ratio'] for o in overhead_metrics)
        avg_delegation_success = mean(o['delegation_success_rate'] for o in overhead_metrics)
    else:
        avg_overhead_ratio = 0
        avg_delegation_success = 0

    # 3. Information Integration Score (per scenario)
    integration_scores = []
    for result in multi_agent_results:
        if result.raw_response:
            score = information_integration_score(result.raw_response)
            integration_scores.append({
                'scenario_id': result.scenario_id,
                'coherence': score.coherence_score,
                'completeness': score.completeness_score,
                'synthesis': score.synthesis_score,
                'overall': score.overall_score
            })

    # Aggregate integration stats
    if integration_scores:
        avg_coherence = mean(s['coherence'] for s in integration_scores)
        avg_completeness = mean(s['completeness'] for s in integration_scores)
        avg_synthesis = mean(s['synthesis'] for s in integration_scores)
        avg_integration = mean(s['overall'] for s in integration_scores)
    else:
        avg_coherence = avg_completeness = avg_synthesis = avg_integration = 0

    return {
        'cooperation_effectiveness': coop_effectiveness,
        'communication_overhead': {
            'per_scenario': overhead_metrics,
            'avg_overhead_ratio': avg_overhead_ratio,
            'avg_delegation_success_rate': avg_delegation_success
        },
        'information_integration': {
            'per_scenario': integration_scores,
            'avg_coherence': avg_coherence,
            'avg_completeness': avg_completeness,
            'avg_synthesis': avg_synthesis,
            'avg_overall': avg_integration
        }
    }


def compare_results(
    baseline_results: List[ScenarioResult],
    multi_agent_results: List[ScenarioResult]
) -> Dict[str, Any]:
    """Perform statistical comparison between baseline and multi-agent results."""

    # Extract metrics
    baseline_mtti = [r.mtti_seconds for r in baseline_results]
    multi_agent_mtti = [r.mtti_seconds for r in multi_agent_results]

    baseline_accuracy = [r.keyword_accuracy for r in baseline_results]
    multi_agent_accuracy = [r.keyword_accuracy for r in multi_agent_results]

    baseline_cross_domain = [r.cross_domain_resolution for r in baseline_results]
    multi_agent_cross_domain = [r.cross_domain_resolution for r in multi_agent_results]

    comparison = {
        'scenario_count': len(baseline_results),
        'timestamp': datetime.now().isoformat(),
        'mtti': {
            'baseline_mean': mean(baseline_mtti),
            'baseline_stdev': stdev(baseline_mtti) if len(baseline_mtti) > 1 else 0,
            'multi_agent_mean': mean(multi_agent_mtti),
            'multi_agent_stdev': stdev(multi_agent_mtti) if len(multi_agent_mtti) > 1 else 0,
            'difference': mean(multi_agent_mtti) - mean(baseline_mtti),
            'overhead_percent': ((mean(multi_agent_mtti) - mean(baseline_mtti)) / mean(baseline_mtti)) * 100
        },
        'keyword_accuracy': {
            'baseline_mean': mean(baseline_accuracy),
            'multi_agent_mean': mean(multi_agent_accuracy),
            'difference': mean(multi_agent_accuracy) - mean(baseline_accuracy)
        },
        'cross_domain_resolution': {
            'baseline_mean': mean(baseline_cross_domain),
            'multi_agent_mean': mean(multi_agent_cross_domain),
            'difference': mean(multi_agent_cross_domain) - mean(baseline_cross_domain)
        },
        'delegation': {
            'multi_agent_delegation_rate': sum(1 for r in multi_agent_results if r.delegation_occurred) / len(multi_agent_results)
        }
    }

    # Statistical tests
    try:
        from scipy import stats

        # Paired t-test for MTTI
        t_stat, p_value = stats.ttest_rel(baseline_mtti, multi_agent_mtti)
        comparison['mtti']['t_statistic'] = t_stat
        comparison['mtti']['p_value'] = p_value
        comparison['mtti']['significant'] = p_value < 0.05

        # Cohen's d
        pooled_std = ((stdev(baseline_mtti)**2 + stdev(multi_agent_mtti)**2) / 2) ** 0.5
        cohens_d = (mean(multi_agent_mtti) - mean(baseline_mtti)) / pooled_std if pooled_std > 0 else 0
        comparison['mtti']['cohens_d'] = cohens_d

        # Paired t-test for accuracy
        t_stat_acc, p_value_acc = stats.ttest_rel(baseline_accuracy, multi_agent_accuracy)
        comparison['keyword_accuracy']['t_statistic'] = t_stat_acc
        comparison['keyword_accuracy']['p_value'] = p_value_acc
        comparison['keyword_accuracy']['significant'] = p_value_acc < 0.05

    except ImportError:
        print("Warning: scipy not available, skipping statistical tests")

    # Per-scenario comparison
    per_scenario = []
    for baseline, multi in zip(baseline_results, multi_agent_results):
        per_scenario.append({
            'scenario_id': baseline.scenario_id,
            'baseline_mtti': baseline.mtti_seconds,
            'multi_agent_mtti': multi.mtti_seconds,
            'mtti_difference': multi.mtti_seconds - baseline.mtti_seconds,
            'baseline_accuracy': baseline.keyword_accuracy,
            'multi_agent_accuracy': multi.keyword_accuracy,
            'accuracy_difference': multi.keyword_accuracy - baseline.keyword_accuracy,
            'baseline_cross_domain': baseline.cross_domain_resolution,
            'multi_agent_cross_domain': multi.cross_domain_resolution,
            'multi_agent_wins_accuracy': multi.keyword_accuracy > baseline.keyword_accuracy,
            'multi_agent_wins_cross_domain': multi.cross_domain_resolution > baseline.cross_domain_resolution
        })

    comparison['per_scenario'] = per_scenario

    # Summary
    comparison['summary'] = {
        'multi_agent_accuracy_wins': sum(1 for s in per_scenario if s['multi_agent_wins_accuracy']),
        'baseline_accuracy_wins': sum(1 for s in per_scenario if s['baseline_accuracy'] > s['multi_agent_accuracy']),
        'accuracy_ties': sum(1 for s in per_scenario if s['accuracy_difference'] == 0),
        'multi_agent_cross_domain_wins': sum(1 for s in per_scenario if s['multi_agent_wins_cross_domain']),
        'baseline_cross_domain_wins': sum(1 for s in per_scenario if s['baseline_cross_domain'] > s['multi_agent_cross_domain'])
    }

    # Add CooperBench metrics
    cooperbench = compute_cooperbench_metrics(baseline_results, multi_agent_results)
    comparison['cooperbench'] = cooperbench

    return comparison


def generate_latex_tables(comparison: Dict[str, Any]) -> str:
    """Generate LaTeX tables for thesis."""
    latex = []

    # Table 1: Aggregate Performance Comparison
    latex.append(r"""
\begin{table}[htbp]
\centering
\caption{Aggregate Performance Comparison: Single-Agent Baseline vs Multi-Agent System}
\label{tab:ab-comparison}
\begin{tabular}{lccc}
\toprule
\textbf{Metric} & \textbf{Baseline} & \textbf{Multi-Agent} & \textbf{Difference} \\
\midrule""")

    mtti = comparison['mtti']
    acc = comparison['keyword_accuracy']
    cross = comparison['cross_domain_resolution']

    latex.append(f"MTTI (seconds) & {mtti['baseline_mean']:.2f} $\\pm$ {mtti['baseline_stdev']:.2f} & {mtti['multi_agent_mean']:.2f} $\\pm$ {mtti['multi_agent_stdev']:.2f} & {mtti['difference']:+.2f} \\\\")
    latex.append(f"Keyword Accuracy & {acc['baseline_mean']:.1%} & {acc['multi_agent_mean']:.1%} & {acc['difference']:+.1%} \\\\")
    latex.append(f"Cross-Domain Resolution & {cross['baseline_mean']:.1%} & {cross['multi_agent_mean']:.1%} & {cross['difference']:+.1%} \\\\")

    latex.append(r"""\bottomrule
\end{tabular}
\end{table}
""")

    # Table 2: Statistical Analysis
    if 't_statistic' in mtti:
        latex.append(r"""
\begin{table}[htbp]
\centering
\caption{Statistical Analysis of Performance Differences}
\label{tab:statistical-analysis}
\begin{tabular}{lcc}
\toprule
\textbf{Metric} & \textbf{MTTI} & \textbf{Keyword Accuracy} \\
\midrule""")

        latex.append(f"t-statistic & {mtti['t_statistic']:.3f} & {acc.get('t_statistic', 'N/A'):.3f} \\\\")
        latex.append(f"p-value & {mtti['p_value']:.4f} & {acc.get('p_value', 'N/A'):.4f} \\\\")
        latex.append(f"Cohen's d & {mtti['cohens_d']:.3f} & -- \\\\")
        sig_mtti = "Yes" if mtti['significant'] else "No"
        sig_acc = "Yes" if acc.get('significant', False) else "No"
        latex.append(f"Significant ($p < 0.05$) & {sig_mtti} & {sig_acc} \\\\")

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

    for s in comparison['per_scenario']:
        latex.append(
            f"{s['scenario_id']} & {s['baseline_mtti']:.1f} & {s['multi_agent_mtti']:.1f} & "
            f"{s['baseline_accuracy']:.0%} & {s['multi_agent_accuracy']:.0%} & "
            f"{s['baseline_cross_domain']:.0%} & {s['multi_agent_cross_domain']:.0%} \\\\"
        )

    latex.append(r"""\bottomrule
\end{tabular}
\end{table}
""")

    # Table 4: CooperBench Metrics (NEW)
    cooperbench = comparison.get('cooperbench', {})
    coop_eff = cooperbench.get('cooperation_effectiveness', {})
    comm_overhead = cooperbench.get('communication_overhead', {})
    integration = cooperbench.get('information_integration', {})

    latex.append(r"""
\begin{table}[htbp]
\centering
\caption{CooperBench-Inspired Cooperation Metrics}
\label{tab:cooperbench-metrics}
\begin{tabular}{lc}
\toprule
\textbf{Metric} & \textbf{Value} \\
\midrule""")

    latex.append(f"Scenarios where MAS wins on accuracy & {coop_eff.get('multi_agent_wins', 0)}/{coop_eff.get('scenario_count', 10)} \\\\")
    latex.append(f"Cooperation Benefit Ratio & {coop_eff.get('cooperation_benefit_ratio', 0):.1%} \\\\")
    latex.append(f"Avg. Accuracy Improvement & {coop_eff.get('avg_accuracy_improvement', 0):+.1%} \\\\")
    latex.append(f"Avg. MTTI Overhead & {coop_eff.get('avg_mtti_overhead_seconds', 0):+.2f}s \\\\")
    latex.append(r"\midrule")
    latex.append(f"Avg. Delegation Overhead Ratio & {comm_overhead.get('avg_overhead_ratio', 0):.1%} \\\\")
    latex.append(f"Delegation Success Rate & {comm_overhead.get('avg_delegation_success_rate', 0):.1%} \\\\")
    latex.append(r"\midrule")
    latex.append(f"Avg. Information Coherence & {integration.get('avg_coherence', 0):.2f} \\\\")
    latex.append(f"Avg. Information Completeness & {integration.get('avg_completeness', 0):.2f} \\\\")
    latex.append(f"Avg. Synthesis Quality & {integration.get('avg_synthesis', 0):.2f} \\\\")
    latex.append(f"Avg. Integration Score & {integration.get('avg_overall', 0):.2f} \\\\")
    latex.append(r"\midrule")
    latex.append(f"Recommendation & {coop_eff.get('recommendation', 'Context-dependent')} \\\\")

    latex.append(r"""\bottomrule
\end{tabular}
\end{table}
""")

    return "\n".join(latex)


def print_summary(comparison: Dict[str, Any]):
    """Print comparison summary to console."""
    print("\n" + "=" * 70)
    print("A/B COMPARISON SUMMARY (with CooperBench Metrics)")
    print("=" * 70)

    mtti = comparison['mtti']
    acc = comparison['keyword_accuracy']
    cross = comparison['cross_domain_resolution']
    summary = comparison['summary']

    print(f"\n{'Metric':<30} {'Baseline':>15} {'Multi-Agent':>15} {'Diff':>10}")
    print("-" * 70)
    print(f"{'MTTI (seconds)':<30} {mtti['baseline_mean']:>15.2f} {mtti['multi_agent_mean']:>15.2f} {mtti['difference']:>+10.2f}")
    print(f"{'Keyword Accuracy':<30} {acc['baseline_mean']:>14.1%} {acc['multi_agent_mean']:>14.1%} {acc['difference']:>+9.1%}")
    print(f"{'Cross-Domain Resolution':<30} {cross['baseline_mean']:>14.1%} {cross['multi_agent_mean']:>14.1%} {cross['difference']:>+9.1%}")

    if 't_statistic' in mtti:
        print(f"\n{'Statistical Significance':}")
        print(f"  MTTI t-statistic: {mtti['t_statistic']:.3f}, p-value: {mtti['p_value']:.4f}")
        print(f"  Cohen's d (effect size): {mtti['cohens_d']:.3f}")
        print(f"  Significant: {'Yes' if mtti['significant'] else 'No'}")

    print(f"\n{'Win/Loss Summary':}")
    print(f"  Multi-agent accuracy wins: {summary['multi_agent_accuracy_wins']}/{comparison['scenario_count']}")
    print(f"  Baseline accuracy wins: {summary['baseline_accuracy_wins']}/{comparison['scenario_count']}")
    print(f"  Ties: {summary['accuracy_ties']}/{comparison['scenario_count']}")

    # CooperBench metrics
    cooperbench = comparison.get('cooperbench', {})
    coop_eff = cooperbench.get('cooperation_effectiveness', {})
    integration = cooperbench.get('information_integration', {})

    print(f"\n{'CooperBench Metrics':}")
    print(f"  Cooperation Benefit Ratio: {coop_eff.get('cooperation_benefit_ratio', 0):.1%}")
    print(f"  Recommendation: {coop_eff.get('recommendation', 'N/A')}")
    print(f"  Avg. Integration Score: {integration.get('avg_overall', 0):.2f}")

    print("\n" + "=" * 70)


def main():
    """Main entry point."""
    print("=" * 70)
    print("Generating Comparison Report from Existing Results")
    print("=" * 70)

    # Find most recent result files
    baseline_files = sorted(RESULTS_DIR.glob("baseline_results_*.json"))
    multi_agent_files = sorted(RESULTS_DIR.glob("multi_agent_results_*.json"))

    if not baseline_files:
        print("ERROR: No baseline results found in", RESULTS_DIR)
        return

    if not multi_agent_files:
        print("ERROR: No multi-agent results found in", RESULTS_DIR)
        return

    # Use most recent files
    baseline_file = baseline_files[-1]
    multi_agent_file = multi_agent_files[-1]

    print(f"\nLoading baseline: {baseline_file.name}")
    print(f"Loading multi-agent: {multi_agent_file.name}")

    # Load results
    baseline_results = load_results(baseline_file)
    multi_agent_results = load_results(multi_agent_file)

    print(f"\nBaseline scenarios: {len(baseline_results)}")
    print(f"Multi-agent scenarios: {len(multi_agent_results)}")

    if len(baseline_results) != len(multi_agent_results):
        print("WARNING: Different number of scenarios!")

    # Generate comparison
    comparison = compare_results(baseline_results, multi_agent_results)

    # Print summary
    print_summary(comparison)

    # Save outputs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save comparison JSON
    comparison_path = RESULTS_DIR / f"comparison_{timestamp}.json"
    with open(comparison_path, 'w') as f:
        json.dump(comparison, f, indent=2, default=str)
    print(f"\nComparison saved to: {comparison_path}")

    # Save LaTeX tables
    latex_tables = generate_latex_tables(comparison)
    latex_path = RESULTS_DIR / f"latex_tables_{timestamp}.tex"
    with open(latex_path, 'w') as f:
        f.write(latex_tables)
    print(f"LaTeX tables saved to: {latex_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
