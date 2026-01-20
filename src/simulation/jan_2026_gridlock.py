"""
Jan 2026 Grid-Lock Scenario Simulation

Purpose:
- Simulates the "Jan 2026 Grid-Lock" infrastructure fault scenario
- Tests the Multi-Agent System's ability to diagnose complex faults
- Measures "Mean Time to Innocence" (MTTI) and diagnostic accuracy
- Generates results for thesis evaluation

Usage:
    python -m src.simulation.jan_2026_gridlock

Metrics Collected:
- Mean Time to Innocence (MTTI) per fault
- Diagnostic accuracy (keyword matching)
- Delegation accuracy (correct agent routing)
- Total simulation time
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

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
MINISTER_URL = "http://localhost:8001/consult"
SCENARIOS_DIR = project_root / "data" / "scenarios"
RESULTS_DIR = project_root / "results"


class GridLockSimulation:
    """Simulation for the Jan 2026 Grid-Lock scenario using HTTP calls to agents."""

    def __init__(self, scenario_file: str = "jan_2026_gridlock.json"):
        """
        Initialize the simulation.

        Args:
            scenario_file: Name of scenario JSON file in data/scenarios/
        """
        self.scenario_file = scenario_file
        self.scenario_data: Optional[Dict[str, Any]] = None
        self.results: Dict[str, Any] = {}
        self.fault_results: List[Dict[str, Any]] = []

    def load_scenario_data(self) -> Dict[str, Any]:
        """
        Load scenario data from JSON file.

        Returns:
            Dictionary containing scenario configuration and faults
        """
        scenario_path = SCENARIOS_DIR / self.scenario_file

        if not scenario_path.exists():
            raise FileNotFoundError(f"Scenario file not found: {scenario_path}")

        logger.info(f"Loading scenario from {scenario_path}")

        with open(scenario_path, 'r') as f:
            self.scenario_data = json.load(f)

        logger.info(f"Loaded scenario: {self.scenario_data.get('scenario_name')}")
        logger.info(f"Faults to test: {len(self.scenario_data.get('faults', []))}")

        return self.scenario_data

    def send_query_to_minister(
        self,
        query: str,
        location: str = "unknown",
        is_symptom: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Send a query to Telekom Minister via HTTP.

        Args:
            query: The diagnostic query
            location: Location context
            is_symptom: Whether this is a symptom/fault report

        Returns:
            Response dictionary if successful, None otherwise
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

        try:
            response = httpx.post(
                MINISTER_URL,
                json=request.model_dump(),
                timeout=60.0
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Request failed with status {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Failed to contact Minister: {e}")
            return None

    def evaluate_diagnosis(
        self,
        response: Dict[str, Any],
        ground_truth: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Evaluate diagnosis accuracy against ground truth.

        Uses keyword matching to score the diagnosis quality.

        Args:
            response: Agent response payload
            ground_truth: Expected diagnosis info

        Returns:
            Dictionary with accuracy metrics
        """
        metrics = {
            "keyword_hits": 0,
            "keyword_total": 0,
            "keyword_accuracy": 0.0,
            "risk_match": False,
            "sla_match": False
        }

        if not response or not ground_truth:
            return metrics

        # Extract response text for keyword matching
        response_card = response.get('response_card', {})
        payload = response_card.get('payload', {})

        # Combine all text fields from response
        response_text = " ".join([
            str(payload.get('answer', '')),
            str(payload.get('risk_level', '')),
            str(payload.get('violated_slas', '')),
            str(payload.get('recommended_actions', '')),
        ]).lower()

        # Also check specialist findings if present
        specialist = payload.get('specialist_findings', {})
        if specialist:
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

        # SLA matching (check if any expected SLAs are mentioned)
        expected_slas = ground_truth.get('violated_slas', [])
        if expected_slas:
            sla_text = str(payload.get('violated_slas', '')).upper()
            metrics["sla_match"] = any(sla in sla_text for sla in expected_slas)
        else:
            # No SLAs expected, check that none were reported
            metrics["sla_match"] = 'none' in str(payload.get('violated_slas', 'none')).lower()

        return metrics

    def evaluate_delegation(
        self,
        response: Dict[str, Any],
        expected_delegation: str
    ) -> bool:
        """
        Check if delegation routing was correct.

        Args:
            response: Agent response
            expected_delegation: Expected target agent ('self', 'siemens_technician', 'illigo_operator')

        Returns:
            True if delegation was correct
        """
        if not response:
            return False

        response_card = response.get('response_card', {})
        payload = response_card.get('payload', {})
        delegation = payload.get('delegation', {})

        actual_target = delegation.get('target_agent', 'self')

        # Check if specialist findings exist (meaning delegation happened)
        specialist = payload.get('specialist_findings')

        if expected_delegation == 'self':
            # Expected no delegation
            return actual_target == 'self' and specialist is None
        else:
            # Expected delegation to specialist
            if specialist:
                spec_card = specialist.get('response_card', {})
                spec_payload = spec_card.get('payload', {})
                actual_agent = spec_payload.get('specialist_agent', '')
                return actual_agent == expected_delegation
            else:
                return actual_target == expected_delegation

    def run_simulation(self) -> Dict[str, Any]:
        """
        Run the complete Grid-Lock simulation.

        Sends each fault query to the Minister and collects metrics.

        Returns:
            Simulation results with aggregated metrics
        """
        logger.info("=" * 60)
        logger.info("Starting Jan 2026 Grid-Lock Simulation")
        logger.info("=" * 60)

        # Load scenario if not already loaded
        if not self.scenario_data:
            self.load_scenario_data()

        faults = self.scenario_data.get('faults', [])
        success_criteria = self.scenario_data.get('success_criteria', {})

        simulation_start = time.time()
        self.fault_results = []

        for i, fault in enumerate(faults, 1):
            fault_id = fault.get('fault_id')
            query = fault.get('query')
            station_id = fault.get('station_id', 'unknown')
            expected_delegation = fault.get('expected_delegation', 'self')
            ground_truth = fault.get('ground_truth', {})

            logger.info(f"\n--- Fault {i}/{len(faults)}: {fault_id} ---")
            logger.info(f"Query: {query[:80]}...")
            logger.info(f"Expected delegation: {expected_delegation}")

            # Time the query
            query_start = time.time()
            response = self.send_query_to_minister(
                query=query,
                location=station_id,
                is_symptom=fault.get('test_type', 'fault_diagnosis') == 'fault_diagnosis'
            )
            query_end = time.time()

            mtti = query_end - query_start

            # Evaluate results
            diagnosis_metrics = self.evaluate_diagnosis(response, ground_truth)
            delegation_correct = self.evaluate_delegation(response, expected_delegation)

            fault_result = {
                "fault_id": fault_id,
                "query": query,
                "station_id": station_id,
                "mtti_seconds": mtti,
                "diagnosis_metrics": diagnosis_metrics,
                "delegation_correct": delegation_correct,
                "expected_delegation": expected_delegation,
                "response_received": response is not None,
                "timestamp": datetime.now().isoformat()
            }

            self.fault_results.append(fault_result)

            logger.info(f"MTTI: {mtti:.2f}s")
            logger.info(f"Keyword accuracy: {diagnosis_metrics['keyword_accuracy']:.1%}")
            logger.info(f"Delegation correct: {delegation_correct}")

        simulation_end = time.time()

        # Calculate aggregate metrics
        total_mtti = sum(r['mtti_seconds'] for r in self.fault_results)
        avg_mtti = total_mtti / len(self.fault_results) if self.fault_results else 0
        avg_accuracy = sum(r['diagnosis_metrics']['keyword_accuracy'] for r in self.fault_results) / len(self.fault_results) if self.fault_results else 0
        delegation_accuracy = sum(1 for r in self.fault_results if r['delegation_correct']) / len(self.fault_results) if self.fault_results else 0

        # Determine success
        mtti_threshold = success_criteria.get('mtti_threshold_seconds', 30)
        accuracy_threshold = success_criteria.get('accuracy_threshold', 0.8)
        delegation_threshold = success_criteria.get('delegation_accuracy_threshold', 0.9)

        success = (
            avg_mtti <= mtti_threshold and
            avg_accuracy >= accuracy_threshold and
            delegation_accuracy >= delegation_threshold
        )

        self.results = {
            "scenario": self.scenario_data.get('scenario_name'),
            "scenario_id": self.scenario_data.get('scenario_id'),
            "timestamp": datetime.now().isoformat(),
            "total_time_seconds": simulation_end - simulation_start,
            "fault_count": len(faults),
            "metrics": {
                "mean_mtti_seconds": avg_mtti,
                "min_mtti_seconds": min(r['mtti_seconds'] for r in self.fault_results) if self.fault_results else 0,
                "max_mtti_seconds": max(r['mtti_seconds'] for r in self.fault_results) if self.fault_results else 0,
                "avg_keyword_accuracy": avg_accuracy,
                "delegation_accuracy": delegation_accuracy,
                "responses_received": sum(1 for r in self.fault_results if r['response_received'])
            },
            "thresholds": {
                "mtti_threshold_seconds": mtti_threshold,
                "accuracy_threshold": accuracy_threshold,
                "delegation_threshold": delegation_threshold
            },
            "success": success,
            "fault_results": self.fault_results
        }

        logger.info("\n" + "=" * 60)
        logger.info("Simulation Complete")
        logger.info("=" * 60)
        logger.info(f"Mean MTTI: {avg_mtti:.2f}s (threshold: {mtti_threshold}s)")
        logger.info(f"Keyword Accuracy: {avg_accuracy:.1%} (threshold: {accuracy_threshold:.0%})")
        logger.info(f"Delegation Accuracy: {delegation_accuracy:.1%} (threshold: {delegation_threshold:.0%})")
        logger.info(f"Overall Success: {'PASS' if success else 'FAIL'}")

        return self.results

    def save_results(self, output_path: Optional[str] = None):
        """
        Save simulation results to JSON file.

        Args:
            output_path: Optional custom output path
        """
        if not output_path:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            output_path = RESULTS_DIR / f"simulation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)

        logger.info(f"Results saved to {output_path}")
        return output_path

    def visualize_results(self, output_dir: Optional[str] = None):
        """
        Generate visualizations of simulation results.

        Creates MTTI distribution chart and accuracy comparison.

        Args:
            output_dir: Directory to save plots
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
        except ImportError:
            logger.warning("matplotlib not available, skipping visualization")
            return

        if not self.fault_results:
            logger.warning("No results to visualize")
            return

        if not output_dir:
            output_dir = RESULTS_DIR / "plots"
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        # Figure 1: MTTI Distribution
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # MTTI bar chart
        fault_ids = [r['fault_id'] for r in self.fault_results]
        mtti_values = [r['mtti_seconds'] for r in self.fault_results]
        threshold = self.results.get('thresholds', {}).get('mtti_threshold_seconds', 30)

        colors = ['green' if m <= threshold else 'red' for m in mtti_values]
        axes[0].bar(fault_ids, mtti_values, color=colors, alpha=0.7, edgecolor='black')
        axes[0].axhline(y=threshold, color='orange', linestyle='--', label=f'Threshold ({threshold}s)')
        axes[0].set_xlabel('Fault ID')
        axes[0].set_ylabel('MTTI (seconds)')
        axes[0].set_title('Mean Time to Innocence (MTTI) per Fault')
        axes[0].legend()
        axes[0].grid(axis='y', alpha=0.3)

        # Accuracy comparison
        metrics_labels = ['Keyword\nAccuracy', 'Delegation\nAccuracy']
        metrics_values = [
            self.results['metrics']['avg_keyword_accuracy'],
            self.results['metrics']['delegation_accuracy']
        ]
        thresholds = [
            self.results['thresholds']['accuracy_threshold'],
            self.results['thresholds']['delegation_threshold']
        ]

        x = range(len(metrics_labels))
        width = 0.35

        axes[1].bar([i - width/2 for i in x], metrics_values, width, label='Achieved', color='steelblue', alpha=0.7)
        axes[1].bar([i + width/2 for i in x], thresholds, width, label='Threshold', color='orange', alpha=0.7)
        axes[1].set_ylabel('Score')
        axes[1].set_title('Accuracy Metrics vs Thresholds')
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(metrics_labels)
        axes[1].legend()
        axes[1].set_ylim(0, 1.1)
        axes[1].grid(axis='y', alpha=0.3)

        # Add value labels
        for i, (val, thresh) in enumerate(zip(metrics_values, thresholds)):
            axes[1].text(i - width/2, val + 0.02, f'{val:.1%}', ha='center', fontsize=9)
            axes[1].text(i + width/2, thresh + 0.02, f'{thresh:.0%}', ha='center', fontsize=9)

        plt.tight_layout()

        plot_path = output_dir / 'mtti_distribution.png'
        plt.savefig(plot_path, dpi=150)
        plt.close()

        logger.info(f"Visualization saved to {plot_path}")

        # Figure 2: Fault-by-fault breakdown
        fig2, ax2 = plt.subplots(figsize=(10, 6))

        keyword_scores = [r['diagnosis_metrics']['keyword_accuracy'] for r in self.fault_results]
        delegation_scores = [1.0 if r['delegation_correct'] else 0.0 for r in self.fault_results]

        x = range(len(fault_ids))
        width = 0.35

        ax2.bar([i - width/2 for i in x], keyword_scores, width, label='Keyword Accuracy', color='steelblue', alpha=0.7)
        ax2.bar([i + width/2 for i in x], delegation_scores, width, label='Delegation Correct', color='seagreen', alpha=0.7)
        ax2.set_xlabel('Fault ID')
        ax2.set_ylabel('Score')
        ax2.set_title('Per-Fault Performance Breakdown')
        ax2.set_xticks(x)
        ax2.set_xticklabels(fault_ids)
        ax2.legend()
        ax2.set_ylim(0, 1.1)
        ax2.grid(axis='y', alpha=0.3)

        plt.tight_layout()

        breakdown_path = output_dir / 'fault_breakdown.png'
        plt.savefig(breakdown_path, dpi=150)
        plt.close()

        logger.info(f"Breakdown chart saved to {breakdown_path}")


def main():
    """Main entry point for running the simulation."""
    print("=" * 60)
    print("Jan 2026 Grid-Lock Simulation")
    print("Multi-Agent System MTTI Evaluation")
    print("=" * 60)
    print()

    # Check if Minister is available
    print("Checking agent availability...")
    try:
        response = httpx.get("http://localhost:8001/health", timeout=5.0)
        if response.status_code != 200:
            print("WARNING: Telekom Minister not responding correctly")
            print("Make sure all agents are running before starting simulation")
            return
        print("Telekom Minister: ONLINE")
    except Exception as e:
        print(f"ERROR: Cannot reach Telekom Minister at localhost:8001")
        print("Please start the agents first:")
        print("  python src/agents/telekom_minister/main.py")
        print("  python src/agents/siemens_technician/main.py")
        print("  python src/agents/illigo_operator/main.py")
        return

    # Run simulation
    sim = GridLockSimulation()

    try:
        results = sim.run_simulation()
        output_path = sim.save_results()

        # Generate visualizations
        sim.visualize_results()

        print()
        print("=" * 60)
        print("Results Summary")
        print("=" * 60)
        print(f"Results saved to: {output_path}")
        print(f"Plots saved to: {RESULTS_DIR / 'plots'}")

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Make sure data/scenarios/jan_2026_gridlock.json exists")
    except Exception as e:
        logger.exception(f"Simulation failed: {e}")


if __name__ == "__main__":
    main()
