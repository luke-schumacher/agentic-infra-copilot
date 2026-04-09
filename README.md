# Agentic Infra Co-Pilot

A **tripartite Multi-Agent System (MAS)** for MRI infrastructure fault diagnosis, built as the primary validation artefact for a Master's thesis at AISS investigating emergent cross-domain reasoning in multi-agent architectures.

> **Current status — 2026-04-09**
> Run 4 complete (60/60 evaluations). Five DSPy output hardening fixes applied (commit `ad30962`). Run 5 is the final thesis evaluation — ready to execute.

---

## Table of Contents

1. [Research Context](#research-context)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Evaluation Framework](#evaluation-framework)
5. [Results Summary — All Runs](#results-summary--all-runs)
6. [Run 4 Results (Pre-Final)](#run-4-results-pre-final)
7. [Architecture Fixes Applied](#architecture-fixes-applied)
8. [DSPy Hardening Fixes (Run 5 Ready)](#dspy-hardening-fixes-run-5-ready)
9. [Project Structure](#project-structure)
10. [Setup](#setup)
11. [Running the System](#running-the-system)
12. [Running the Evaluation](#running-the-evaluation)
13. [API Reference](#api-reference)
14. [Troubleshooting](#troubleshooting)
15. [Key Documents](#key-documents)

---

## Research Context

### Thesis

**Domain-agnostic critical infrastructure diagnostics via multi-agent emergence**, validated on Siemens Healthineers MRI operations data (40 customer installations, MAGNETOM operator manuals, DICOM conformance documentation, safety PDFs).

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
2. The MAS response contains explicit cross-domain references, OR the LLM-as-Judge cross_domain score exceeds 0.5

The dual criterion prevents false negatives from fragile keyword detection.

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
              │  ChromaDB: 418 docs       │
              └──────┬──────────┬────────┘
                     │CONSULT   │PARTIAL / REDIRECT
           ┌─────────▼──┐  ┌───▼──────────┐
           │  Hardware   │  │  Telemetry   │
           │   Agent     │  │    Agent     │  :8003
           │  :8002      │  │              │
           │ MRI · DICOM │  │ Event logs · │
           │ 9,853 docs  │  │ 945 docs     │
           └──────┬──────┘  └──────┬───────┘
                  └────────┬────────┘
                           │ findings_dict
                           ▼
              ┌──────────────────────────┐
              │   DiagnosisSynthesizer    │
              │   (DSPy ChainOfThought)   │  ← no HTTP, no RAG
              │   Claude Sonnet 4.6       │  ← unified_diagnosis < 300 words
              └──────────────────────────┘
```

### Agent Responsibilities

| Agent | Port | Domain | Knowledge Base |
|-------|------|---------|----------------|
| **Governance** | 8001 | SLA compliance, uptime targets, clinical protocols, institutional policy | Institution profiles, workload patterns, SLA documents (418 docs) |
| **Hardware** | 8002 | MRI hardware errors, DICOM conformance, thermal management, Phoenix Protocol | MAGNETOM operator manuals, DICOM Conformance Statements, safety PDFs (9,853 docs) |
| **Telemetry** | 8003 | MRI event logs, session monitoring, temporal fault patterns, safety zones | Safety procedures, zone access rules, session metrics (945 docs) |

### Autonomy Protocol

Before answering any query, each agent evaluates the request using its `EvaluateRequest` DSPy signature (via router LM) and returns one of six response types:

| Response Type | Meaning | Orchestrator Action |
|---------------|---------|---------------------|
| `ANSWER` | Complete, confident response | Finalise if confidence ≥ 0.5; else consult remaining agents |
| `PARTIAL` | Incomplete — more context needed | Consult remaining agents in parallel |
| `CONSULT` | Wants a specific peer agent's input | Call suggested agent (+ remaining in parallel) |
| `REDIRECT` | Wrong agent for this query | Route to suggested agent |
| `CLARIFY` | Needs information from the user | Surface clarification questions |
| `REFUSE` | Cannot or should not answer | Try remaining agents |

### Multi-Round Orchestration

```
run_diagnosis()
  └─ _call_agent(governance)              # always entry point
      └─ orchestrate_round()
          ├─ ANSWER (high confidence) → _finalize_diagnosis()
          ├─ ANSWER (low confidence)  → _call_agents_parallel(unconsulted)
          ├─ CONSULT                  → _call_agents_parallel([suggested] + remaining)
          ├─ PARTIAL                  → _call_agents_parallel(unconsulted)
          ├─ REDIRECT                 → _call_agents_parallel([suggested] + remaining)
          └─ REFUSE                   → _call_agents_parallel(unconsulted)

All finalisation paths:
  _finalize_diagnosis()          → synthesizer.synthesize(query, findings_dict)
  _synthesize_partial_findings() → synthesizer.synthesize(query, findings_dict)
  _synthesize_best_effort()      → synthesizer.synthesize(query, findings_dict)
```

Maximum 4 rounds. Retry logic: 3 attempts at 20 s / 45 s / 90 s (total 155 s) for HTTP 429, 502, 503, 504, 529 (Anthropic overload).

---

## Technology Stack

| Layer | Technology | Role |
|-------|-----------|------|
| **Reasoner** | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) | All agent domain reasoning, LLM-as-Judge |
| **Synthesiser** | Claude Sonnet 4.6 (`claude-sonnet-4-6`) | Final cross-domain synthesis in MAS mode |
| **Router** | Azure OpenAI GPT-4.1 | Request classification, delegation routing |
| **Agent framework** | DSPy 2.5+ | Signature-based prompting, ChainOfThought |
| **Agent services** | FastAPI + Uvicorn | Three microservices on :8001–:8003 |
| **HTTP client** | httpx (async) | Inter-agent communication |
| **Vector store** | ChromaDB | Per-domain RAG retrieval |
| **Embeddings** | sentence-transformers (`all-MiniLM-L6-v2`) | Document and query embedding |
| **UI** | Streamlit | Interactive diagnostic interface on :8501 |
| **Schema** | Pydantic v2 | `AgentCard`, `AgentResponse`, `DiagnosisSession` |
| **Containers** | Docker Compose | Three-service deployment |

### Three-Tier Model Strategy (`src/agents/shared/dspy_config.py`)

```python
# Hybrid mode: Azure GPT-4.1 router + Anthropic Haiku reasoner + Anthropic Sonnet synthesiser
router_lm    = dspy.LM("openai/gpt-4.1",                      temperature=0.0)
reasoner_lm  = dspy.LM("anthropic/claude-haiku-4-5-20251001", temperature=0.1)
synthesizer_lm = dspy.LM("anthropic/claude-sonnet-4-6",       temperature=0.1)
dspy.configure(lm=reasoner_lm)  # Haiku is global default
```

---

## Evaluation Framework

### 5-Mode Ablation

Every test case is executed in five modes to isolate the effect of data access versus agent collaboration:

| Mode | Agents | Data Access | Purpose |
|------|--------|-------------|---------|
| `governance_only` | Governance only | Governance store | Single-domain ceiling |
| `hardware_only` | Hardware only | Hardware store | Single-domain ceiling |
| `telemetry_only` | Telemetry only | Telemetry store | Single-domain ceiling |
| `single_all_data` | Governance only | **All three stores merged** | **Critical baseline** — isolates collaboration value from data access |
| `mas_full` | All three | Domain-specific stores | **System under test** |

The key comparison is `mas_full` vs `single_all_data`. If MAS wins, the value comes from structured collaboration, not just data aggregation.

### 12 Test Cases

Distributed across three difficulty levels:

| Difficulty | Count | Characteristic |
|-----------|-------|----------------|
| Simple | 2 | Single-domain fault, one expected agent |
| Moderate | 5 | Two-domain fault, consultation expected |
| Complex | 5 | Three-domain fault, full MAS required for complete diagnosis |

Test cases: `cascading_thermal_fault`, `phantom_load_spike`, `gradient_coil_degradation`, `helium_boiloff_cascade`, `shimming_environmental`, `multi_scanner_cooling`, `software_update_regression`, `rf_amplifier_intermittent`, `network_false_alarm`, `protocol_conflict_sla`, `missed_maintenance_escalation`, `known_fault_code_lookup`.

### Scoring Instruments

| Instrument | Method | What it captures |
|-----------|--------|-----------------|
| **Keyword accuracy** | Ground-truth keyword matching | Diagnostic precision (primary metric) |
| **LLM-as-Judge (4D)** | Claude Haiku scores accuracy, relevance, completeness, cross_domain | Qualitative response quality |
| **Semantic similarity** | Sentence-transformer cosine vs reference diagnosis | Meaning-level fidelity |
| **Latency** | Wall-clock time per evaluation | Orchestration overhead |
| **Emergence margin** | MAS accuracy − best single-agent accuracy | Core emergence signal |

---

## Results Summary — All Runs

| Run | Date | Status | MAS Acc | Best Single | Emergence | Key change |
|-----|------|--------|---------|------------|-----------|------------|
| Run 1 | 2026-02-23 | ❌ Infrastructure bugs | — | — | — | Payload extraction, keyword mapping, baseline routing broken |
| Run 2 | 2026-02-24 | ✅ 60/60 | 58.3% | 81.7% (SAD) | 0/12 | First complete run; root cause: concatenation not synthesis |
| Run 3 | 2026-04-08 | ❌ Agents offline | ~58% | — | 0/12 | Hardware/telemetry containers not running; 0% for both |
| Run 4 | 2026-04-08 | ✅ 60/60 | **53.3%** | **50.0%** (SAD) | **2/12** | All three agents active; first positive emergence; 5 cases still 0% |
| **Run 5** | pending | 🔄 Ready | — | — | — | DSPy None hardening (5 bugs fixed) |

**Cross-run trajectory:**
- Run 2 emergence margin: −23.4 pp (MAS 58.3% vs SAD 81.7%)
- Run 4 emergence margin: **+3.3 pp** (MAS 53.3% vs SAD 50.0%) — first positive emergence overall

---

## Run 4 Results (Pre-Final)

### Aggregate Scores

| Mode | Keyword Acc | Judge Score | Semantic Sim | Avg Latency |
|------|:-----------:|:-----------:|:------------:|:-----------:|
| Governance Only | 33.3% | 43.2% | 5.6% | 109.8 s |
| Hardware Only | 43.3% | 41.0% | 7.8% | 15.2 s |
| Telemetry Only | 36.7% | 41.5% | 4.5% | 15.0 s |
| **Single + All Data** | **50.0%** | **47.9%** | **6.1%** | 79.2 s |
| **Full MAS** | **53.3%** | **55.5%** | **3.3%** | 102.2 s |

MAS outperforms Single + All Data by **+3.3 pp** — a reversal from Run 2.

### Emergence Cases (Run 4)

| Test Case | Difficulty | MAS | Best Single | Margin | Cross-domain refs |
|-----------|-----------|-----|------------|:------:|:-----------------:|
| `gradient_coil_degradation` | complex | 80% | 60% (hw/tel) | **+20 pp** | 6 |
| `helium_boiloff_cascade` | complex | 100% | 80% (hw/sad) | **+20 pp** | 8 |

### Per-Case Breakdown

| Test Case | Gov | Hw | Tel | SAD | **MAS** | Emergence |
|-----------|-----|-----|-----|-----|---------|:---------:|
| cascading_thermal_fault | 80% | 80% | 80% | 80% | **80%** | — |
| phantom_load_spike | 20% | 60% | 60% | 100% | **100%** | — |
| gradient_coil_degradation | 40% | 60% | 60% | 60% | **80%** | ✓ |
| helium_boiloff_cascade | 40% | 80% | 60% | 80% | **100%** | ✓ |
| shimming_environmental | 40% | 80% | 40% | 100% | **100%** | — |
| multi_scanner_cooling | 80% | 100% | 60% | 100% | **100%** | — |
| software_update_regression | 40% | 60% | 80% | 80% | **80%** | — |
| rf_amplifier_intermittent | 60% | 0%* | 0%* | 0%* | **0%*** | — |
| network_false_alarm | 0%* | 0%* | 0%* | 0%* | **0%*** | — |
| protocol_conflict_sla | 0%* | 0%* | 0%* | 0%* | **0%*** | — |
| missed_maintenance_escalation | 0%* | 0%* | 0%* | 0%* | **0%*** | — |
| known_fault_code_lookup | 0%* | 0%* | 0%* | 0%* | **0%*** | — |

*\* = DSPy None output failure, fixed in commit `ad30962`*

### MAS Agent Participation (Run 4)

- All three agents consulted: 12/12 (100%)
- Average rounds: 1.0
- Governance consulted: 12/12
- Hardware consulted: 12/12
- Telemetry consulted: 12/12

---

## Architecture Fixes Applied

The following architectural fixes were implemented between Run 2 and Run 4:

### Fix 1 — DSPy Synthesis Module (Run 2 → Run 3)

Replaced governance-agent-based synthesis with a dedicated `DiagnosisSynthesizer` class (`src/orchestration/synthesis.py`) using DSPy `ChainOfThought` over Claude Sonnet 4.6. Pure LLM reasoning — no HTTP call, no RAG retrieval. All three finalisation methods now call `synthesizer.synthesize(query, findings_dict)`.

### Fix 2 — Parallel Agent Execution (Run 2 → Run 3)

Added `_call_agents_parallel()` via `asyncio.gather()`. Hardware and Telemetry operate on non-overlapping domains and are safe to parallelise. Reduced expected MAS latency from `sum(agent_times)` to `max(t_hw, t_tel) + t_synth`.

### Fix 3 — Context Injection Parity (Run 2 → Run 3)

MAS mode previously passed only `governance_context` in the query while `single_all_data` received all three domain contexts. Fixed to include all three in the MAS query, eliminating the data-access confound.

### Fix 4 — Inter-Mode Delay (Run 3)

Increased from 10 s to 30 s between ablation modes within each test case. The 10 s gap was insufficient for the Anthropic token-budget window to partially reset between governance (which consumed the per-minute budget) and hardware/telemetry.

### Fix 5 — Between-Case Delay (Run 3/4)

Increased `DELAY_BETWEEN_CASES_S` from 2 s to 45 s between test cases.

### Fix 6 — Live Consult Probe in Preflight (Run 3/4)

Extended preflight from `/health`-only to include a real `/consult` request to each agent. Verifies end-to-end DSPy processing, not just HTTP availability. Uses 120 s timeout to accommodate DSPy cold-start. Run 3 failed because `/health` passed while DSPy was not initialised.

---

## DSPy Hardening Fixes (Run 5 Ready)

Five bugs causing empty DSPy output for 5/12 test cases were identified in Run 4 post-analysis and fixed in commit `ad30962`:

### Bug 1 — `getattr` None Leakage (All 3 Agents)

`getattr(result, field, default)` returns `None` (not `default`) when a DSPy Prediction attribute exists but is `None`. Every response payload field now uses `getattr(result, field, default) or default`.

### Bug 2 — `float(None)` TypeError on Confidence Extraction (All 3 Agents)

`float(getattr(evaluation, 'confidence_level', ...))` crashed when DSPy returned `None` for `confidence_level`. Replaced with safe extraction and try/except fallback to `0.8`.

### Bug 3 — Narrow Findings Extraction

`multi_round.py` only checked 4 payload keys; symptom queries never have `answer`. Expanded to all 14 known payload keys across all three agents and all query types.

### Bug 4 — Fallback String Masking

Agent `getattr` defaults (`'Unknown'`, `'None identified'`, etc.) are truthy and would terminate the `or`-chain before real content fields. Added `_real()` helper to filter fallback strings. Reordered `institution_profile` to last (weakest signal).

### Bug 5 — `_is_empty_response` Gaps

`single_all_data` mode accepted `"No findings from governance_agent"` and fallback strings as valid responses. Extended `_is_empty_response()` to catch all agent fallback strings and the `"no findings from"` prefix, allowing correct fallthrough to hardware/telemetry.

**Full technical details:** See `docs/evaluation-process-log.md`.

---

## Project Structure

```
agentic-infra-copilot/
│
├── src/
│   ├── agents/
│   │   ├── governance_agent/           # :8001 — SLA & policy
│   │   │   ├── main.py                 # FastAPI app, /consult endpoint
│   │   │   ├── brain.py                # DSPy signatures (ProfileInstitution,
│   │   │   │                           #   AnalyzeWorkloadPattern, EvaluateRequest...)
│   │   │   ├── clinical_governance_loader.py
│   │   │   └── store.py
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
│   │   └── shared/
│   │       └── dspy_config.py          # Three-tier LM config (Haiku + Sonnet + GPT-4.1)
│   │
│   ├── orchestration/
│   │   ├── multi_round.py              # MultiRoundOrchestrator — parallel calls,
│   │   │                               #   retry logic, 14-key findings extraction,
│   │   │                               #   _real() fallback filter
│   │   └── synthesis.py                # DiagnosisSynthesizer (DSPy CoT, Sonnet)
│   │
│   ├── evaluation/
│   │   ├── run_evaluation.py           # Top-level CLI (--dry-run, --test-case,
│   │   │                               #   --no-resume, --modes); live consult probe
│   │   ├── ablation_runner.py          # 5-mode runner, _is_empty_response (hardened),
│   │   │                               #   single_all_data fallthrough logic
│   │   ├── emergence_tests.py          # 12 EmergenceTestCase definitions
│   │   ├── judge.py                    # LLM-as-Judge (4D scoring via Claude Haiku)
│   │   ├── metrics.py                  # Semantic similarity (sentence-transformers)
│   │   └── diagnosis_logging.py        # DiagnosisLog schema + keyword scorer
│   │
│   ├── protocol/
│   │   └── schema.py                   # AgentCard, AgentResponse, DiagnosisSession,
│   │                                   #   ResponseType, AgentRole, IntentType, Priority
│   │
│   ├── retrieval/
│   │   ├── vector_store.py
│   │   └── embeddings.py
│   │
│   ├── ingestion/                      # Data loaders (PDF, CSV, JSON, Parquet)
│   │   ├── pdf_parser.py
│   │   ├── siemens_loader.py
│   │   └── siemens_eventlog_parser.py
│   │
│   └── ui/
│       └── app.py                      # Streamlit diagnostic UI (:8501)
│
├── results/
│   └── ablation/
│       ├── thesis_summary.json         # ★ Run 4 aggregate results (60 evaluations)
│       ├── *_ablation.json (×12)       # Per-test-case detailed breakdowns
│       └── *_mas_full.json             # Individual MAS session traces
│
├── chroma_db/
│   ├── governance_agent/               # 418 governance documents
│   ├── hardware_agent/                 # 9,853 hardware documents
│   └── telemetry_agent/                # 945 telemetry documents
│
├── docs/
│   ├── evaluation-process-log.md       # ★ Complete audit trail of all runs and fixes
│   ├── plans/
│   │   └── 2026-02-04-mas-architecture-evaluation-design.md
│   ├── MAS_ASSESSMENT.md
│   ├── HOW_TO_RUN.md
│   └── DEPLOYMENT.md
│
├── tests/
│   ├── test_delegation_e2e.py
│   └── test_ingestion.py
│
├── docker-compose.yml                  # Three-service deployment
├── requirements.txt
└── Dockerfile
```

---

## Setup

### Prerequisites

- Python 3.10+
- Docker + Docker Compose (for containerised deployment)
- Anthropic API key (Claude Haiku 4.5 reasoning + Claude Sonnet 4.6 synthesis)
- Azure OpenAI API key (GPT-4.1 routing)

### Install

```bash
git clone <repository-url>
cd agentic-infra-copilot
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
# Required
ANTHROPIC_API_KEY=your_anthropic_key_here
AZURE_OPENAI_API_KEY=your_azure_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# Optional
BASELINE_MODE=false          # set true to disable delegation in governance agent
LOG_LEVEL=INFO
```

---

## Running the System

### Via Docker Compose (Recommended)

```bash
# Start all three agents
docker compose up --build

# Or start in background
docker compose up -d --build
```

Wait for all three services to initialise (~60–90 s for DSPy cold-start).

### Manual (Development)

```bash
# Terminal 1 — Governance Agent (:8001)
python -m uvicorn src.agents.governance_agent.main:app --host 0.0.0.0 --port 8001

# Terminal 2 — Hardware Agent (:8002)
python -m uvicorn src.agents.hardware_agent.main:app --host 0.0.0.0 --port 8002

# Terminal 3 — Telemetry Agent (:8003)
python -m uvicorn src.agents.telemetry_agent.main:app --host 0.0.0.0 --port 8003
```

### Verify Health

```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

---

## Running the Evaluation

### Preflight Check (Always Run First)

```bash
# Verifies /health AND live /consult probe for all three agents
# Will FAIL if DSPy is still initialising — wait and retry
python -m src.evaluation.run_evaluation --dry-run
```

Expected passing output:
```
✓ governance_agent  status=healthy  docs=418   consult=OK
✓ hardware_agent    status=healthy  docs=9853  consult=OK
✓ telemetry_agent   status=healthy  docs=945   consult=OK
All agents healthy. Ready to evaluate.
```

### Full Run (Run 5 — Final Thesis Evaluation)

```bash
# Delete previous results first
rm -f results/ablation/*_ablation.json results/ablation/thesis_summary.json

# Full 60-evaluation run (12 cases × 5 modes)
# Takes ~60–120 min depending on API rate limits
python -m src.evaluation.run_evaluation --no-resume
```

### Single Test Case

```bash
# One test case across all 5 modes
python -m src.evaluation.run_evaluation --test-case cascading_thermal_fault --no-resume

# One test case in specific modes
python -m src.evaluation.run_evaluation --test-case gradient_coil_degradation --modes mas_full single_all_data
```

### Resume an Interrupted Run

```bash
# Resumes from last completed test case (default behaviour)
python -m src.evaluation.run_evaluation
```

---

## API Reference

Each agent exposes the same endpoint pattern:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Agent info and status |
| `/health` | GET | Health check — confirms vector store is loaded |
| `/consult` | POST | Submit a diagnostic query |
| `/index` | POST | Re-index domain documents |
| `/documents/count` | GET | Number of indexed documents |

### `/consult` Request

```json
{
  "card": {
    "sender": "orchestrator",
    "recipient": "governance_agent",
    "intent": "diagnose",
    "priority": "high",
    "payload": {
      "query": "MRI scanner showing 94% uptime vs 99% SLA target with intermittent thermal alerts",
      "context": {
        "accumulated_context": "",
        "is_consultation": false,
        "expertise_needed": ""
      }
    }
  },
  "await_response": true
}
```

### `/consult` Response

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
      "risk_factors": "string",
      "recommended_actions": "string"
    }
  }
}
```

The orchestrator checks payload keys in priority order via the `_real()` filter (see `src/orchestration/multi_round.py` lines 174–203).

---

## Troubleshooting

### Preflight probe fails — `consult=FAIL`

The agent HTTP server is up but DSPy has not finished initialising. Wait 60–90 s and retry. Do not start evaluation until the probe passes.

### `float(None)` TypeError

Fixed in `ad30962`. All three agents now use safe confidence extraction. If you see this in older code, upgrade to commit `ad30962` or later.

### Empty findings — `"No findings from {agent}"`

Fixed in `ad30962`. The orchestrator now checks 14 payload keys via the `_real()` filter. If you see this with current code, the DSPy output for all fields is genuinely None for that case.

### `ANTHROPIC_API_KEY not found`

Create `.env` in the project root with `ANTHROPIC_API_KEY=...` and `AZURE_OPENAI_API_KEY=...`.

### Evaluation timeout / retry exhaustion (155 s per case)

Agents are not responding. Check that all three Docker containers are running (`docker ps`). The 155 s pattern (`20 + 45 + 90`) is the fingerprint of retry exhaustion, not slow responses.

### Port already in use

```bash
# Find and kill process on port 8001
lsof -ti:8001 | xargs kill -9   # Linux/Mac
netstat -ano | findstr :8001    # Windows (then taskkill /PID <pid> /F)
```

---

## Key Documents

| File | Contents |
|------|----------|
| `docs/evaluation-process-log.md` | ★ **Complete audit trail** — all runs, all bugs, all fixes with code. Thesis appendix reference. |
| `results/ablation/thesis_summary.json` | Run 4 aggregate metrics (60 evaluations) |
| `results/ablation/*_ablation.json` | Per-test-case mode breakdowns |
| `src/orchestration/synthesis.py` | DiagnosisSynthesizer (DSPy CoT, Sonnet) |
| `src/orchestration/multi_round.py` | Full orchestration with parallel execution and hardened findings extraction |
| `src/evaluation/emergence_tests.py` | All 12 test case definitions |
| `src/agents/shared/dspy_config.py` | Three-tier model configuration |
| `docs/plans/2026-02-04-mas-architecture-evaluation-design.md` | Architecture specification |

---

## Evaluation Run History

| Run | Date | Evaluations | Status | MAS / SAD | Emergence | Key outcome |
|-----|------|-------------|--------|-----------|-----------|-------------|
| Run 1 | 2026-02-23 | 60 attempted | ❌ Bugs | — | — | Payload extraction, keyword mapping, baseline routing broken |
| Run 2 | 2026-02-24 | 60/60 ✓ | ✅ Complete | 58.3% / 81.7% | 0/12 | Root cause: concatenation not synthesis; −23.4 pp margin |
| Run 3 | 2026-04-08 | 60/60 ✓ | ❌ Invalid | ~58% / — | 0/12 | Hardware/telemetry containers offline; 0% for both agents |
| Run 4 | 2026-04-08 | 60/60 ✓ | ✅ Valid | 53.3% / 50.0% | **2/12** | First positive emergence; 5 cases still 0% (DSPy None bug) |
| **Run 5** | pending | 60 planned | 🔄 Ready | — | — | 5 DSPy hardening bugs fixed (`ad30962`); final thesis run |

---

## Acknowledgements

- **Siemens Healthineers** — primary validation partner; MRI operations data, DICOM conformance statements, MAGNETOM operator manuals, safety documentation
- **Deutsche Telekom** — background infrastructure data (network intent, SLA documentation)
- **Illigo** — background data (operational scheduling)

---

*Master's thesis — AISS programme. Full evaluation audit trail: `docs/evaluation-process-log.md`.*
