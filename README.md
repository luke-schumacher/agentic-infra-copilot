# Agentic Infra Co-Pilot

A **tripartite Multi-Agent System (MAS)** for MRI infrastructure fault diagnosis, built as the primary validation artefact for a Master's thesis at AISS investigating emergent cross-domain reasoning in multi-agent architectures.

> **Current status — 2026-02-25**
> Run 2 complete (60/60 evaluations, zero timeouts). Synthesis architecture fix implemented. Run 3 pending.

---

## Table of Contents

1. [Research Context](#research-context)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Evaluation Framework](#evaluation-framework)
5. [Results — Run 2](#results--run-2-2026-02-24)
6. [Architecture Fix — Synthesis Module](#architecture-fix--synthesis-module-run-3-ready)
7. [Project Structure](#project-structure)
8. [Setup](#setup)
9. [Running the System](#running-the-system)
10. [Running the Evaluation](#running-the-evaluation)
11. [API Reference](#api-reference)
12. [Troubleshooting](#troubleshooting)
13. [Key Documents](#key-documents)

---

## Research Context

### Thesis

**Domain-agnostic critical infrastructure diagnostics via multi-agent emergence**, validated on Siemens Healthineers MRI operations data (40 customer installations, machine manuals, DICOM conformance documentation).

**Validation partner**: Siemens Healthineers (primary). Deutsche Telekom and Illigo (background data).

### Research Questions

| # | Question |
|---|----------|
| RQ1 | Can a tripartite MAS produce emergent diagnostic capabilities that no individual agent can achieve alone? |
| RQ2 | How does MAS performance compare to a single-agent baseline with equivalent data access, across query difficulty levels? |
| RQ3 | What is the latency/accuracy trade-off of multi-round agent orchestration, and can it be mitigated through parallel execution? |

### Emergence Definition

Emergence is demonstrated when **both** of the following hold simultaneously:
1. MAS keyword accuracy exceeds the best single-agent accuracy across all four non-MAS modes (positive *emergence margin*)
2. The MAS response contains explicit cross-domain references — reasoning chains that connect concepts from at least two agent domains

---

## System Architecture

### Three Specialist Agents

Each agent runs as an independent FastAPI microservice with its own domain-specific ChromaDB vector store.

```
┌─────────────────────────────────────────────────────────────────┐
│                    User / Streamlit UI (:8501)                   │
└────────────────────────────┬────────────────────────────────────┘
                             │ query
                             ▼
              ┌──────────────────────────┐
              │    Governance Agent       │  :8001
              │  SLA · Policies · Intent  │  ← always called first
              │  ChromaDB: governance/    │
              └──────┬──────────┬────────┘
                     │CONSULT   │REDIRECT / PARTIAL
           ┌─────────▼──┐  ┌───▼──────────┐
           │  Hardware   │  │  Telemetry   │
           │   Agent     │  │    Agent     │  :8003
           │  :8002      │  │              │
           │ MRI · DICOM │  │ Event logs · │
           │ Thermal     │  │ Sessions ·   │
           │ ChromaDB:   │  │ Patterns     │
           │ hardware/   │  │ ChromaDB:    │
           └──────┬──────┘  │ telemetry/   │
                  │          └──────┬───────┘
                  └────────┬────────┘
                           │ findings_dict
                           ▼
              ┌──────────────────────────┐
              │   DiagnosisSynthesizer    │
              │   (DSPy ChainOfThought)   │  ← no HTTP, no RAG
              │   unified_diagnosis       │  ← <300 words
              └──────────────────────────┘
```

### Agent Responsibilities

| Agent | Port | Domain | Knowledge Base |
|-------|------|---------|----------------|
| **Governance** | 8001 | SLA compliance, uptime targets, clinical protocols, institutional policy | Institution profiles, workload patterns, SLA documents |
| **Hardware** | 8002 | MRI hardware errors, DICOM conformance, thermal management, Phoenix Protocol | Siemens manuals, DICOM Conformance Statements, error catalogs |
| **Telemetry** | 8003 | MRI event logs, session monitoring, temporal fault patterns, safety zones | Safety procedures, zone access rules, session metrics |

### Autonomy Protocol

Before answering any query, each agent evaluates the request and returns one of six response types:

| Response Type | Meaning | Orchestrator Action |
|---------------|---------|---------------------|
| `ANSWER` | Complete, confident response | Finalize if confidence ≥ 0.8 |
| `PARTIAL` | Incomplete — more context needed | Consult remaining agents in parallel |
| `CONSULT` | Wants a specific peer agent's input | Call suggested agent (+ remaining in parallel) |
| `REDIRECT` | Wrong agent for this query | Route to suggested agent |
| `CLARIFY` | Needs information from the user | Surface clarification questions |
| `REFUSE` | Cannot or should not answer | Try remaining agents |

This prevents hallucination cascades and provides measurable signals for evaluation (response type distribution per mode).

### Multi-Round Orchestration

```
run_diagnosis()
  └─ _call_agent(governance)           # always entry point
      └─ orchestrate_round()
          ├─ ANSWER (high confidence) → _finalize_diagnosis()
          ├─ ANSWER (low confidence)  → _call_agents_parallel(unconsulted)
          ├─ CONSULT                  → _call_agents_parallel([suggested] + remaining)
          ├─ PARTIAL                  → _call_agents_parallel(unconsulted)
          ├─ REDIRECT                 → _call_agents_parallel([suggested] + remaining)
          └─ REFUSE                   → _call_agents_parallel(unconsulted)

All finalization paths:
  _finalize_diagnosis()         → synthesizer.synthesize(query, findings_dict)
  _synthesize_partial_findings()→ synthesizer.synthesize(query, findings_dict)
  _synthesize_best_effort()     → synthesizer.synthesize(query, findings_dict)
```

Maximum 4 rounds. Retry logic: 3 attempts at 3 s / 8 s / 15 s for HTTP 429, 502, 503, 504, 529.

---

## Technology Stack

| Layer | Technology | Role |
|-------|-----------|------|
| **Reasoning** | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) | All agent reasoning, synthesis, LLM-as-Judge |
| **Routing** | GPT-4.1-nano (`openai/gpt-4.1-nano`) | Request classification, intent routing |
| **Agent framework** | DSPy 2.5+ | Signature-based prompting, ChainOfThought |
| **Agent services** | FastAPI + Uvicorn | Three microservices on :8001–:8003 |
| **HTTP client** | httpx (async) | Inter-agent communication |
| **Vector store** | ChromaDB | Per-domain RAG retrieval |
| **Embeddings** | sentence-transformers (`all-MiniLM-L6-v2`) | Document and query embedding |
| **UI** | Streamlit | Interactive diagnostic interface on :8501 |
| **Schema** | Pydantic v2 | `AgentCard`, `AgentResponse`, `DiagnosisSession` |
| **Graph DB** | Neo4j | Built but not used in ablation evaluation |

### Model Configuration (`src/agents/shared/dspy_config.py`)

```python
# Two-tier strategy
router_lm  = dspy.LM("openai/gpt-4.1-nano",                    temperature=0.0)
reasoner_lm = dspy.LM("anthropic/claude-haiku-4-5-20251001",   temperature=0.1)
dspy.configure(lm=reasoner_lm)   # Claude is global default
```

---

## Evaluation Framework

### 5-Mode Ablation

Every test case is executed in five modes to isolate the effect of data access and agent collaboration:

| Mode | Agents | Data Access | Purpose |
|------|--------|-------------|---------|
| `governance_only` | Governance only | Governance store | Single-domain ceiling |
| `hardware_only` | Hardware only | Hardware store | Single-domain ceiling |
| `telemetry_only` | Telemetry only | Telemetry store | Single-domain ceiling |
| `single_all_data` | Governance only | **All three stores merged** | **The critical baseline** — isolates collaboration value from data access |
| `mas_full` | All three | Domain-specific stores | **The system under test** |

The key comparison is `mas_full` vs `single_all_data`. If MAS wins, the value comes from structured collaboration, not just data aggregation.

### 12 Test Cases

Distributed across three difficulty levels:

| Difficulty | Count | Characteristic |
|-----------|-------|----------------|
| Simple | 4 | Single-domain fault, one expected agent |
| Moderate | 4 | Two-domain fault, consultation expected |
| Complex | 4 | Three-domain fault, full MAS required for complete diagnosis |

Test cases include: `cascading_thermal_fault`, `phantom_load_spike`, `known_fault_code_lookup`, `helium_boiloff_cascade`, `gradient_coil_degradation`, `missed_maintenance_escalation`, `rf_amplifier_intermittent`, `protocol_conflict_sla`, `network_false_alarm`, `software_update_regression`, `multi_scanner_cooling`, `shimming_environmental`.

### Scoring Instruments

| Instrument | Method | What it captures |
|-----------|--------|-----------------|
| **Keyword accuracy** | Ground-truth keyword matching against expected terms | Diagnostic precision — are the right concepts present? |
| **LLM-as-Judge (4D)** | Claude Haiku 4.5 scores accuracy, relevance, completeness, cross_domain (0–1 each) | Qualitative response quality |
| **Semantic similarity** | Sentence-transformer cosine vs reference diagnosis | Meaning-level fidelity |
| **Latency** | Wall-clock time per evaluation | Orchestration overhead |
| **Emergence margin** | MAS keyword accuracy − best single-agent keyword accuracy | Core emergence signal |

---

## Results — Run 2 (2026-02-24)

> Run 1 (2026-02-23) identified three infrastructure bugs (payload extraction, keyword mapping, baseline routing) and was discarded. Run 2 corrected all three and completed all 60 evaluations with zero timeouts.

### Aggregate Scores

| Mode | Keyword Acc | Judge Score | Semantic Sim | Avg Latency |
|------|:-----------:|:-----------:|:------------:|:-----------:|
| Governance Only | 48.3% | 66.9% | 54.5% | 97.9 s |
| Hardware Only | 73.3% | 78.2% | 68.3% | 16.7 s |
| Telemetry Only | 53.3% | 41.3% | 41.0% | 13.9 s |
| **Single + All Data** | **81.7%** | **87.8%** | **70.5%** | 87.5 s |
| Full MAS | 58.3% | 69.4% | 49.8% | 303.4 s |

Single agent with all data beats the MAS by **23.4 percentage points** on keyword accuracy.

### Emergence Analysis

**0 / 12 test cases demonstrated emergence.**

| Difficulty | MAS avg | Best single avg | Emergence margin |
|-----------|---------|-----------------|:----------------:|
| Simple | 30% | 60% | **−30%** |
| Moderate | 64% | 88% | **−24%** |
| Complex | 64% | 88% | **−24%** |

All margins are negative across all difficulty levels — the penalty is not task-complexity-dependent.

### Latency Breakdown

| Metric | Value |
|--------|-------|
| MAS average | 303.4 s |
| Single + All Data | 87.5 s |
| MAS overhead | +215.9 s (+247%) |
| Worst case (`missed_maintenance_escalation`) | 524.7 s |
| Avg rounds per MAS evaluation | 1.67 |
| Governance consulted | 12/12 (100%) |
| Hardware consulted | 11/12 (92%) |
| Telemetry consulted | 9/12 (75%) |

### The Key Finding: Reasoning vs Assembly

Despite low accuracy scores, MAS **LLM-as-Judge cross-domain scores ranged 0.33–0.92 (mean ≈ 0.70)**, indicating that agents genuinely produce cross-domain reasoning.

**The dissociation:**
- Agents **do** produce cross-domain insights (high judge cross-domain scores)
- But the final output is agent-prefixed **concatenation** — `governance_agent: [...] hardware_agent: [...]`
- This dilutes keyword density, introduces competing framings, and confuses both scoring instruments

**Best case — `cascading_thermal_fault`:** 6-point cross-domain analysis (equipment age, duty cycles, maintenance gaps, software cascades, hub pressure, SLA mismatch). Judge cross-domain score: 0.92. Keyword accuracy: 80% — same as the single-agent baseline. Zero positive margin.

**Worst case — `phantom_load_spike`:** Single agent 100%, MAS 40%. Hardware said sensor drift, Telemetry said scheduling artifacts — contradictory explanations with no synthesis step to resolve them.

---

## Architecture Fix — Synthesis Module (Run 3 Ready)

### Root Cause

The previous `_run_synthesis_round()` called the Governance Agent to synthesise findings, but Governance ran fresh RAG retrieval against its vector store instead of reasoning over the provided text. It produced a fourth independent agent response, not an integration step.

All three finalization methods (`_finalize_diagnosis`, `_synthesize_partial_findings`, `_synthesize_best_effort`) concatenated agent outputs with prefixes rather than synthesising them.

### Fix 1 — DSPy Synthesis Module (`src/orchestration/synthesis.py`)

```python
class SynthesizeDiagnosis(dspy.Signature):
    """Synthesize findings from multiple specialist agents into one unified diagnosis."""
    original_query: str = dspy.InputField(desc="The original diagnostic query")
    agent_findings: str = dspy.InputField(desc="Labeled findings from each specialist agent")
    unified_diagnosis: str = dspy.OutputField(
        desc="Concise integrated root-cause diagnosis with cross-domain connections "
             "and recommended actions in under 300 words"
    )
```

- Pure LLM reasoning over provided evidence — **no HTTP call, no RAG retrieval**
- Uses Claude Haiku 4.5 (already globally configured via `dspy.configure()`)
- Falls back to concatenation if synthesis fails — safe degradation
- All three finalization methods now call `self.synthesizer.synthesize(query, findings_dict)`

### Fix 2 — Parallel Agent Execution (`src/orchestration/multi_round.py`)

Old (serial): `t_gov + t_hw + t_tel ≈ 303 s average`

New (parallel): `t_gov + max(t_hw, t_tel) + t_synth`

Hardware and Telemetry operate on non-overlapping knowledge domains, making their analyses independent and safe to parallelise via `asyncio.gather()`.

```python
async def _call_agents_parallel(self, agent_ids, query, context, ...):
    tasks = [self._call_agent(aid, query, context) for aid in agent_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # exceptions → REFUSE responses, not crashes
```

Expected latency reduction: **~100–120 s off MAS average**.

### Fix 3 — Removed `_run_synthesis_round()`

The governance-based synthesis round is removed entirely. The `run_diagnosis()` loop no longer calls it.

### Expected Run 3 Outcomes

| Metric | Run 2 | Run 3 target | Mechanism |
|--------|-------|-------------|-----------|
| MAS keyword accuracy | 58.3% | ≥ 75% | Synthesis concentrates keywords |
| MAS judge score | 69.4% | ≥ 80% | No competing framings |
| MAS latency | 303 s | ~150–200 s | Parallel hw + tel calls |
| Emergence | 0/12 | ≥ 1/12 | Synthesis surfaces buried cross-domain keywords |

---

## Project Structure

```
agentic-infra-copilot/
│
├── src/
│   ├── agents/
│   │   ├── governance_agent/           # :8001 — SLA & policy
│   │   │   ├── main.py                 # FastAPI app, /consult endpoint
│   │   │   ├── brain.py                # DSPy signatures (EvaluateRequest,
│   │   │   │                           #   DiagnoseCompliance, DelegateToSpecialist...)
│   │   │   ├── clinical_governance_loader.py
│   │   │   └── store.py                # ChromaDB vector store wrapper
│   │   │
│   │   ├── hardware_agent/             # :8002 — MRI hardware & DICOM
│   │   │   ├── main.py
│   │   │   ├── brain.py                # DSPy signatures (AnalyzeHardwareError,
│   │   │   │                           #   DiagnoseDICOMFailure, LookupTechnicalSpec...)
│   │   │   ├── mri_hardware_loader.py
│   │   │   └── store.py
│   │   │
│   │   ├── telemetry_agent/            # :8003 — Event logs & safety
│   │   │   ├── main.py
│   │   │   ├── brain.py                # DSPy signatures (ValidateComplianceSOP,
│   │   │   │                           #   ReviewDiagnosticAction, CheckSafetyZone...)
│   │   │   ├── mri_data_loader.py
│   │   │   └── store.py
│   │   │
│   │   ├── baseline/
│   │   │   └── unified_store.py        # Merged vector store for single_all_data mode
│   │   │                               # activated via BASELINE_MODE=true env var
│   │   └── shared/
│   │       └── dspy_config.py          # Two-tier LM setup (Claude Haiku + GPT-4.1-nano)
│   │
│   ├── orchestration/
│   │   ├── multi_round.py              # MultiRoundOrchestrator — parallel calls,
│   │   │                               #   all response types, retry logic
│   │   └── synthesis.py                # ★ NEW — DiagnosisSynthesizer (DSPy CoT)
│   │
│   ├── evaluation/
│   │   ├── run_evaluation.py           # Top-level CLI (--dry-run, --test-case,
│   │   │                               #   --no-resume, --modes)
│   │   ├── ablation_runner.py          # 5-mode runner, mode switching, logging
│   │   ├── emergence_tests.py          # 12 EmergenceTestCase definitions
│   │   ├── judge.py                    # LLM-as-Judge (4D scoring via Claude Haiku)
│   │   ├── metrics.py                  # Semantic similarity (sentence-transformers)
│   │   └── diagnosis_logging.py        # DiagnosisLog schema + keyword scorer
│   │
│   ├── protocol/
│   │   ├── schema.py                   # AgentCard, AgentResponse, DiagnosisSession,
│   │   │                               #   ResponseType, AgentRole, IntentType, Priority
│   │   └── output_schema.py
│   │
│   ├── retrieval/
│   │   ├── vector_store.py             # ChromaDB wrapper
│   │   └── embeddings.py               # sentence-transformer embedding util
│   │
│   ├── ingestion/                      # Data loaders (PDF, CSV, JSON, Parquet)
│   │   ├── pdf_parser.py
│   │   ├── siemens_loader.py
│   │   ├── siemens_eventlog_parser.py
│   │   └── ...
│   │
│   ├── preprocessing/                  # Domain-specific preprocessors
│   │   ├── siemens_preprocessor.py
│   │   └── ...
│   │
│   └── ui/
│       └── app.py                      # Streamlit diagnostic UI (:8501)
│
├── results/
│   ├── ablation/
│   │   ├── thesis_summary.json         # ★ Run 2 aggregate results (60 evaluations)
│   │   ├── *_ablation.json (×12)       # Per-test-case detailed breakdowns
│   │   └── *.json (UUID files)         # Individual MAS session logs
│   └── ab_comparison/                  # Earlier A/B comparison runs (pre-ablation)
│
├── logs/
│   └── diagnosis/                      # Per-session diagnosis traces (UUID-named)
│
├── data/
│   ├── processed/
│   │   ├── customer_mapping.csv        # 40 Siemens customer installations
│   │   └── ...
│   └── scenarios/
│       └── cross_domain_evaluation.json
│
├── docs/
│   ├── plans/
│   │   └── 2026-02-04-mas-architecture-evaluation-design.md  # Architecture spec
│   ├── logs/
│   │   └── 2026-02-23-evaluation-run.md                       # Run 1 log
│   ├── MAS_ASSESSMENT.md               # Multi-agent system assessment
│   ├── MAS_BEST_PRACTICES.md
│   ├── HOW_TO_RUN.md                   # Detailed run guide
│   └── DEPLOYMENT.md
│
├── notebooks/
│   ├── thesis_comprehensive_eda.ipynb  # Full EDA notebook
│   └── *.ipynb                         # Domain-specific EDA
│
├── tests/
│   ├── test_delegation_e2e.py
│   └── test_ingestion.py
│
├── config/
│   ├── .env.example                    # Environment variable template
│   └── config.yaml
│
├── RESULTS_SUMMARY.md                  # ★ 10-min verbal summary of Run 2 results
├── SESSION_SUMMARY.md
├── Cooperbench.md
├── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

---

## Setup

### Prerequisites

- Python 3.10+
- Anthropic API key (Claude Haiku 4.5 — reasoning + judge)
- OpenAI API key (GPT-4.1-nano — routing)

### Install

```bash
git clone <repository-url>
cd agentic-infra-copilot
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root (not `config/`):

```env
# Required
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here

# Optional — controls single_all_data baseline mode
BASELINE_MODE=false          # set true to disable delegation in governance agent

# Optional — logging
LOG_LEVEL=INFO
```

The system uses `python-dotenv` — `.env` in the project root is loaded automatically.

### Verify DSPy Configuration

```bash
python -c "
from src.agents.shared.dspy_config import configure_dspy
cfg = configure_dspy()
print('Router:', cfg.router.model)
print('Reasoner:', cfg.reasoner.model)
"
```

Expected output:
```
Router: openai/gpt-4.1-nano
Reasoner: anthropic/claude-haiku-4-5-20251001
```

---

## Running the System

### 1. Start the Three Agents

Open three terminal windows (or use `&` for background):

```bash
# Terminal 1 — Governance Agent (:8001)
python -m uvicorn src.agents.governance_agent.main:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2 — Hardware Agent (:8002)
python -m uvicorn src.agents.hardware_agent.main:app --host 0.0.0.0 --port 8002 --reload

# Terminal 3 — Telemetry Agent (:8003)
python -m uvicorn src.agents.telemetry_agent.main:app --host 0.0.0.0 --port 8003 --reload
```

### 2. Verify Health

```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

Expected response from each:
```json
{"status": "healthy", "agent": "governance_agent", "documents_loaded": true}
```

### 3. Start the UI (Optional)

```bash
streamlit run src/ui/app.py --server.port 8501
```

Open `http://localhost:8501` in your browser.

### 4. Send a Test Query

```bash
curl -X POST http://localhost:8001/consult \
  -H "Content-Type: application/json" \
  -d '{
    "card": {
      "sender": "orchestrator",
      "recipient": "governance_agent",
      "intent": "diagnose",
      "priority": "high",
      "payload": {
        "query": "MRI scanner showing 94% uptime vs 99% SLA target with intermittent thermal alerts",
        "context": {"accumulated_context": "", "is_consultation": false}
      }
    },
    "await_response": true
  }'
```

---

## Running the Evaluation

### Quick Checks

```bash
# Verify synthesis module imports correctly (post-fix)
python -c "from src.orchestration.synthesis import DiagnosisSynthesizer; print('OK')"

# Health check all agents (dry run — no LLM calls)
python -m src.evaluation.run_evaluation --dry-run
```

### Single Test Case

```bash
# Run one test case across all 5 modes
python -m src.evaluation.run_evaluation --test-case cascading_thermal_fault --no-resume

# Run one test case in specific modes only
python -m src.evaluation.run_evaluation --test-case cascading_thermal_fault --modes mas_full single_all_data
```

### Full Ablation (Run 3)

```bash
# Full 60-evaluation run (12 cases × 5 modes)
# Takes ~60–90 min depending on API rate limits
python -m src.evaluation.run_evaluation --no-resume
```

Results are written to `results/ablation/` as each test case completes.
Aggregate summary: `results/ablation/thesis_summary.json`.

### Resume an Interrupted Run

```bash
# Resume from last completed test case (default behaviour)
python -m src.evaluation.run_evaluation
```

### Comparing Run 2 vs Run 3

```python
import json

run2 = json.load(open("results/ablation/thesis_summary_run2.json"))
run3 = json.load(open("results/ablation/thesis_summary.json"))

for mode in ["mas_full", "single_all_data"]:
    r2 = run2["mode_averages"][mode]
    r3 = run3["mode_averages"][mode]
    delta = r3["accuracy"] - r2["accuracy"]
    print(f"{mode}: {r2['accuracy']:.1%} → {r3['accuracy']:.1%} ({delta:+.1%})")
```

---

## API Reference

Each agent exposes the same endpoint pattern:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Agent info and status |
| `/health` | GET | Health check — confirms vector store is loaded |
| `/consult` | POST | Submit a diagnostic query (primary evaluation endpoint) |
| `/index` | POST | Re-index domain documents into ChromaDB |
| `/documents/count` | GET | Number of indexed documents |
| `/documents/search` | GET | Search the vector store directly |

### `/consult` Request Schema

```json
{
  "card": {
    "sender": "orchestrator",
    "recipient": "governance_agent",
    "intent": "diagnose",
    "priority": "high",
    "payload": {
      "query": "string",
      "context": {
        "accumulated_context": "string",
        "is_consultation": false,
        "expertise_needed": "string"
      }
    }
  },
  "await_response": true
}
```

### `/consult` Response Schema

```json
{
  "response_card": {
    "response_type": "answer | partial | consult | redirect | clarify | refuse",
    "confidence": 0.85,
    "suggested_agent": "hardware_agent | null",
    "payload": {
      "contextual_explanation": "string",
      "root_cause": "string",
      "diagnosis": "string",
      "reasoning": "string",
      "missing_info": "string",
      "consultation_reason": "string"
    }
  }
}
```

The orchestrator checks payload keys in priority order: `contextual_explanation → root_cause → diagnosis → answer`.

---

## Troubleshooting

### `ANTHROPIC_API_KEY not found`
Create `.env` in the project root with `ANTHROPIC_API_KEY=...` and `OPENAI_API_KEY=...`.

### `DSPy not configured. Call configure_dspy() first.`
`configure_dspy()` is called at agent startup. If using the synthesizer standalone, call it explicitly:
```python
from src.agents.shared.dspy_config import configure_dspy
configure_dspy()
```

### Agent returns empty `findings`
The payload key mismatch was fixed in Run 2. The orchestrator now checks `contextual_explanation`, `root_cause`, `diagnosis`, and `answer` in order. If you're seeing empty findings, check the raw response payload from the agent's `/consult` endpoint.

### `BASELINE_MODE` not working
Set `BASELINE_MODE=true` in your `.env` **before** starting the Governance Agent. The agent reads this at startup; changing it mid-run requires a restart.

### Evaluation timeout
Default per-call timeout is 120 s with 3 retries. If Claude or OpenAI rate-limits are frequent, increase the timeout in `MultiRoundOrchestrator`:
```python
orchestrator = MultiRoundOrchestrator(timeout_seconds=180.0)
```

### Port already in use
```bash
# Windows — find process on port 8001
netstat -ano | findstr :8001

# Kill by PID
taskkill /PID <pid> /F
```

### Vector store not loading
Each agent indexes on startup. If documents aren't loading, check that the ChromaDB path is writable and the raw data files exist in `data/raw/<domain>/`.

---

## Key Documents

| File | Contents |
|------|----------|
| `RESULTS_SUMMARY.md` | Condensed 10-minute briefing on Run 2 findings and Run 3 plan |
| `results/ablation/thesis_summary.json` | Full Run 2 aggregate metrics (60 evaluations) |
| `docs/plans/2026-02-04-mas-architecture-evaluation-design.md` | Architecture specification and evaluation design |
| `docs/MAS_ASSESSMENT.md` | Multi-agent system assessment and CooperBench context |
| `docs/logs/2026-02-23-evaluation-run.md` | Run 1 session log (bugged run, retained for audit trail) |
| `src/orchestration/synthesis.py` | DSPy synthesis module (Run 3 fix) |
| `src/orchestration/multi_round.py` | Full orchestration logic with parallel execution |
| `src/evaluation/emergence_tests.py` | All 12 test case definitions |
| `src/agents/shared/dspy_config.py` | Model configuration (Claude Haiku + GPT-4.1-nano) |

---

## Evaluation Run History

| Run | Date | Evaluations | Status | Key outcome |
|-----|------|-------------|--------|-------------|
| Run 1 | 2026-02-23 | 60 attempted | ❌ Infrastructure bugs | Payload extraction failure, keyword mapping errors, baseline routing broken |
| Run 2 | 2026-02-24 | 60/60 ✓ | ✅ Complete | MAS 58.3% vs baseline 81.7%; 0/12 emergence; root cause: concatenation not synthesis |
| Run 3 | Pending | 60 planned | 🔄 Ready | Synthesis fix + parallel execution; target ≥75% MAS accuracy |

---

## Acknowledgements

- **Siemens Healthineers** — primary validation partner; MRI operations data, DICOM conformance statements, machine manuals
- **Deutsche Telekom** — background infrastructure data (network intent, SLA documentation)
- **Illigo** — background data (operational scheduling)

---

*Master's thesis — AISS programme. See `docs/` for architecture plans, deployment guides, and session logs.*
