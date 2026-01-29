import json
import matplotlib.pyplot as plt
import numpy as np
from src.simulation.ab_comparison import ABComparisonRunner, ScenarioResult

def generate_report():
    runner = ABComparisonRunner()

    # 1. DEFINE YOUR FILE PATHS
    multi_agent_path = 'results/ab_comparison/multi_agent_results_20260129_125550.json'
    baseline_path =    'results/ab_comparison/baseline_results_20260129_152303.json'

    print(f"Loading Multi-Agent: {multi_agent_path}")
    print(f"Loading Baseline:    {baseline_path}")

    # 2. LOAD AND CONVERT DATA (Fixes the "object vs dict" error)
    try:
        with open(multi_agent_path, 'r') as f:
            data = json.load(f)
            # Convert raw dicts back to ScenarioResult objects
            runner.multi_agent_results = [ScenarioResult(**item) for item in data]
            
        with open(baseline_path, 'r') as f:
            data = json.load(f)
            runner.baseline_results = [ScenarioResult(**item) for item in data]
            
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    # 3. RUN COMPARISON
    print("Generating statistical comparison...")
    comparison = runner.compare_results()
    
    # 4. PRINT SUMMARY TO TERMINAL
    runner.print_summary(comparison)
    
    # 5. GENERATE CHARTS (The missing feature)
    print("\nGenerating charts...")
    create_charts(runner.baseline_results, runner.multi_agent_results)

def create_charts(baseline, multi_agent):
    """Draws bar charts comparing MTTI and Accuracy."""
    
    # Prepare data
    scenarios = [r.scenario_id for r in baseline]
    
    baseline_mtti = [r.mtti_seconds for r in baseline]
    multi_mtti = [r.mtti_seconds for r in multi_agent]
    
    baseline_acc = [r.keyword_accuracy * 100 for r in baseline]
    multi_acc = [r.keyword_accuracy * 100 for r in multi_agent]

    x = np.arange(len(scenarios))
    width = 0.35

    # --- CHART 1: MTTI (Response Time) ---
    fig, ax = plt.subplots(figsize=(12, 6))
    rects1 = ax.bar(x - width/2, baseline_mtti, width, label='Baseline', color='gray')
    rects2 = ax.bar(x + width/2, multi_mtti, width, label='Multi-Agent', color='#0078D7') # Telecom Blue

    ax.set_ylabel('Response Time (seconds)')
    ax.set_title('MTTI Comparison: Single vs Multi-Agent')
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, rotation=45)
    ax.legend()
    
    plt.tight_layout()
    plt.savefig('results/ab_comparison/comparison_mtti.png')
    print("Saved: results/ab_comparison/comparison_mtti.png")

    # --- CHART 2: Accuracy ---
    fig, ax = plt.subplots(figsize=(12, 6))
    rects1 = ax.bar(x - width/2, baseline_acc, width, label='Baseline', color='gray')
    rects2 = ax.bar(x + width/2, multi_acc, width, label='Multi-Agent', color='#28a745') # Success Green

    ax.set_ylabel('Accuracy (%)')
    ax.set_title('Keyword Accuracy Comparison')
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, rotation=45)
    ax.legend()

    plt.tight_layout()
    plt.savefig('results/ab_comparison/comparison_accuracy.png')
    print("Saved: results/ab_comparison/comparison_accuracy.png")

if __name__ == "__main__":
    generate_report()