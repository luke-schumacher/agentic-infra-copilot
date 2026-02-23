# Agentic Infra Co-Pilot

A Multi-Agent System (MAS) for healthcare MRI infrastructure fault diagnosis, validated through a 5-mode ablation study proving emergent cross-domain reasoning.

## Project Overview

**Agentic Infra Co-Pilot** is a distributed **Multi-Agent System (MAS)** designed to autonomously diagnose complex infrastructure faults. It orchestrates three specialized AI agents that collaborate to synthesize information across domains that no single agent can fully cover:

1. **Governance Agent**: Clinical workflow analysis, SLA compliance, institutional policy enforcement.
2. **Hardware Agent**: MRI equipment diagnostics, component lifecycle tracking, manufacturer advisory analysis.
3. **Telemetry Agent**: Event log monitoring, temporal pattern detection, anomaly identification.

The system uses **DSPy + Groq (Llama-3.3-70B)** for reasoning, **ChromaDB** for RAG retrieval, and a **multi-round orchestration protocol** enabling emergent diagnosis through agent collaboration.

## Key Features

- **Multi-Agent Architecture**: Three specialized FastAPI agents (ports 8001-8003) with domain-specific RAG.
- **Multi-Round Orchestration**: Governance-led dialogue protocol with CONSULT/PARTIAL/REDIRECT response types enabling cross-domain synthesis.
- **5-Mode Ablation Study**: Systematic comparison across governance-only, hardware-only, telemetry-only, single-agent-all-data, and full MAS modes.
- **12 Emergence Test Cases**: Healthcare MRI scenarios (simple/moderate/complex) designed to require cross-domain reasoning.
- **Automated Evaluation**: LLM-as-Judge (4D scoring), semantic similarity, keyword accuracy, and emergence detection.
- **Streamlit UI**: Interactive diagnostic interface (port 8501).
- **Resume-Capable Evaluation Runner**: CLI tool with health checks, resume support, and thesis-formatted output.

## Project Structure

```
agentic-infra-copilot/
├── src/
│   ├── agents/
│   │   ├── governance_agent/       # Port 8001 - Clinical workflow & SLA
│   │   │   ├── main.py             # FastAPI service
│   │   │   ├── brain.py            # DSPy reasoning module
│   │   │   ├── clinical_governance_loader.py
│   │   │   └── store.py            # ChromaDB vector store
│   │   ├── hardware_agent/         # Port 8002 - MRI equipment diagnostics
│   │   │   ├── main.py
│   │   │   ├── brain.py
│   │   │   ├── mri_hardware_loader.py
│   │   │   └── store.py
│   │   ├── telemetry_agent/        # Port 8003 - Event log analysis
│   │   │   ├── main.py
│   │   │   ├── brain.py
│   │   │   ├── mri_data_loader.py
│   │   │   └── store.py
│   │   ├── baseline/               # Single-agent baseline mode
│   │   │   └── unified_store.py    # Unified vector store (all domains)
│   │   └── shared/                 # Shared DSPy config
│   │
│   ├── evaluation/                 # Thesis evaluation framework
│   │   ├── run_evaluation.py       # Top-level orchestrator (CLI)
│   │   ├── ablation_runner.py      # 5-mode ablation test runner
│   │   ├── emergence_tests.py      # 12 test case definitions
│   │   ├── judge.py                # LLM-as-Judge (4D scoring)
│   │   ├── metrics.py              # Semantic similarity metrics
│   │   └── diagnosis_logging.py    # Structured diagnosis logs
│   │
│   ├── orchestration/
│   │   └── multi_round.py          # Multi-round dialogue orchestrator
│   │
│   ├── protocol/
│   │   └── schema.py               # Pydantic models (AgentCard, etc.)
│   │
│   └── ui/
│       └── streamlit_app.py        # Streamlit diagnostic UI (port 8501)
│
├── data/
│   ├── raw/siemens/                # Siemens MRI data (PDFs, manuals)
│   └── processed/                  # Processed domain data
│       ├── governance/             # Institution profiles, workload stats
│       ├── hardware/               # Equipment specs, DICOM metadata
│       └── telemetry/              # Event logs, session metrics
│
├── results/ablation/               # Evaluation output
│   ├── *_ablation.json (x12)       # Per-test-case results
│   └── thesis_summary.json         # Aggregate thesis metrics
│
├── docs/
│   ├── plans/                      # Architecture & design docs
│   ├── logs/                       # Session logs
│   └── *.md                        # Reference documentation
│
├── tests/                          # Test suite
├── config/                         # Configuration files
└── requirements.txt
```

## Quick Start

### Prerequisites

- Python 3.10+
- Groq API key (for Llama-3.3-70B inference)

### Setup

```bash
git clone <repository-url>
cd agentic-infra-copilot
pip install -r requirements.txt

# Set environment variables
export GROQ_API_KEY=your_key_here
```

### Running the Agents

```bash
# Start all three agents
python -m uvicorn src.agents.governance_agent.main:app --port 8001 &
python -m uvicorn src.agents.hardware_agent.main:app --port 8002 &
python -m uvicorn src.agents.telemetry_agent.main:app --port 8003 &

# Start the UI (optional)
streamlit run src/ui/streamlit_app.py --server.port 8501
```

### Running the Evaluation

```bash
# Health check only
python -m src.evaluation.run_evaluation --dry-run

# Single test case
python -m src.evaluation.run_evaluation --test-case cascading_thermal_fault

# Full 12-case suite (60 evaluations, ~1 hour)
python -m src.evaluation.run_evaluation

# Rerun everything (ignore cached results)
python -m src.evaluation.run_evaluation --no-resume
```

## Evaluation Framework

### 5-Mode Ablation Design

Each of the 12 test cases is run in five modes to measure emergence:

| Mode | Description |
|------|-------------|
| `governance_only` | Single agent with governance data only |
| `hardware_only` | Single agent with hardware data only |
| `telemetry_only` | Single agent with telemetry data only |
| `single_all_data` | One agent with all three domains combined |
| `mas_full` | All three agents collaborating via multi-round protocol |

**Emergence** is demonstrated when: `MAS accuracy > max(single-agent accuracies)` AND `cross_domain_refs > 0`.

### Metrics Collected

| Metric | Method | Granularity |
|--------|--------|-------------|
| Keyword accuracy | Ground-truth keyword matching | test case x mode |
| LLM-as-Judge 4D | accuracy, relevance, completeness, cross-domain | test case x mode |
| Semantic similarity | Sentence-transformer cosine similarity | test case x mode |
| Emergence margin | MAS accuracy - best single agent | test case |
| Latency | Wall-clock time per evaluation | test case x mode |
| Rounds used | Multi-round orchestration rounds | test case (MAS) |

### Latest Results (2026-02-23)

| Mode | Avg Accuracy | Avg Judge | Avg Semantic |
|------|-------------|-----------|-------------|
| governance_only | 0.0% | 0.03 | 0.08 |
| hardware_only | 16.7% | 0.21 | 0.31 |
| telemetry_only | 20.0% | 0.17 | 0.28 |
| single_all_data | 0.0% | 0.01 | 0.10 |
| **mas_full** | **23.3%** | **0.22** | **0.24** |

Emergence demonstrated in 1/12 cases. MAS outperformed best single agent on simple (+20%) and moderate (+12%) difficulty cases. See [full evaluation log](docs/logs/2026-02-23-evaluation-run.md).

## Thesis Context

This project is part of a Master's thesis at AISS investigating domain-agnostic multi-agent emergence for critical infrastructure diagnostics, validated on Siemens Healthineers MRI operations data. The evaluation framework answers:

- **RQ1**: Does multi-agent collaboration produce emergent diagnostic capabilities?
- **RQ2**: How does MAS performance compare to single-agent baselines across difficulty levels?
- **RQ3**: What is the latency/accuracy trade-off of multi-agent orchestration?

## Development

```bash
pytest tests/ -v
```

## Acknowledgments

- Siemens Healthineers for MRI operations data (primary validation partner)
- Deutsche Telekom and Illigo (background data partners)

---

**Note:** This is a research project for a Master's thesis. See `docs/` for architecture plans, deployment guides, and session logs.
