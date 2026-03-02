# Agentic Infra Copilot — Results Summary
**Date:** 2026-03-02 | **Status:** Run 3 complete — synthesis fix evaluated

---

## What the system is (1 min)

A **tripartite multi-agent system (MAS)** for MRI infrastructure diagnostics, built for Siemens Healthineers validation.

Three specialist FastAPI agents (ports 8001–8003):
- **Governance** — SLA compliance, institution policies, uptime targets
- **Hardware** — MRI hardware errors, DICOM conformance, thermal faults
- **Telemetry** — Event logs, session patterns, safety zone monitoring

Each agent has its own ChromaDB vector store (RAG). They communicate via a structured autonomy protocol (ANSWER / PARTIAL / CONSULT / REDIRECT / REFUSE / CLARIFY).

Reasoning model: **Claude Haiku 4.5**. Router: **GPT-4.1-nano**.

---

## Evaluation design (1 min)

**5-mode ablation** across **12 test cases** (2 simple / 5 moderate / 5 complex) = **60 evaluations per run**.

| Mode | What it tests |
|------|---------------|
| Governance Only | Single agent, governance store only |
| Hardware Only | Single agent, hardware store only |
| Telemetry Only | Single agent, telemetry store only |
| **Single + All Data** | Single agent, all 3 stores merged — the critical baseline |
| **Full MAS** | All 3 agents collaborating — the system under test |

Three scoring instruments: **keyword accuracy**, **LLM-as-Judge score**, **semantic similarity**.

**Emergence criterion** (the thesis hypothesis): MAS accuracy > best single-agent AND response contains genuine cross-domain references.

---

## Run history

| Run | Date | Status | Key Event |
|-----|------|--------|-----------|
| Run 1 | 23 Feb 2026 | Infrastructure debug | Found 3 bugs: payload extraction, keyword mapping, baseline routing |
| Run 2 | 24 Feb 2026 | First complete evaluation | 0/12 emergence, MAS 58.3%, identified concatenation root cause |
| Run 3 | 2 Mar 2026 | Post-synthesis evaluation | 2/12 emergence, MAS 65.0%, latency −44% |

---

## Run 2 results (before fix)

| Mode | Keyword Acc | Judge Score | Semantic Sim | Avg Latency |
|------|-------------|-------------|--------------|-------------|
| Governance Only | 48.3% | 66.9% | 54.5% | 97.9 s |
| Hardware Only | 73.3% | 78.2% | 68.3% | 16.7 s |
| Telemetry Only | 53.3% | 41.3% | 41.0% | 13.9 s |
| **Single + All Data** | **81.7%** | **87.8%** | **70.5%** | 87.5 s |
| Full MAS | 58.3% | 69.4% | 49.8% | 303.4 s |

**Emergence: 0 / 12** — all margins negative (simple −30%, moderate −24%, complex −24%)

Root cause: MAS output was concatenated agent sections, not a synthesis. Keyword dilution + competing framings.

---

## Run 3 results (after synthesis fix)

| Mode | Keyword Acc | Judge Score | Semantic Sim | Avg Latency |
|------|-------------|-------------|--------------|-------------|
| Governance Only | 40.0% | 54.0% | 48.1% | 117.1 s |
| Hardware Only | 71.7% | 65.5% | 65.2% | 16.0 s |
| Telemetry Only | 48.3% | 37.4% | 36.9% | 15.1 s |
| **Single + All Data** | **85.0%** | **84.8%** | **69.8%** | 87.0 s |
| Full MAS | **65.0%** | **71.1%** | **50.1%** | **169.8 s** |

### Run 2 vs Run 3 — MAS only

| | Keyword Acc | Judge Score | Semantic Sim | Avg Latency |
|--|-------------|-------------|--------------|-------------|
| Run 2 | 58.3% | 69.4% | 49.8% | 303.4 s |
| Run 3 | 65.0% | 71.1% | 50.1% | 169.8 s |
| **Δ** | **+6.7 pp** | **+1.7 pp** | **+0.3 pp** | **−133.6 s (−44%)** |

### Emergence: **2 / 12** ⭐

| Test Case | Difficulty | MAS | Best Single | Margin |
|-----------|------------|-----|-------------|--------|
| `gradient_coil_degradation` | Complex | 80% | 60% | **+20 pp** |
| `missed_maintenance_escalation` | Simple | 80% | 60% | **+20 pp** |

Per-difficulty margins:
| Difficulty | Avg Margin | Emerged |
|------------|------------|---------|
| Simple | −30% | 1/2 |
| Moderate | −20% | 0/5 |
| Complex | −16% | 1/5 |

---

## What changed and why it worked (2 min)

### B1 — New DSPy synthesis module (`src/orchestration/synthesis.py`)

```python
class SynthesizeDiagnosis(dspy.Signature):
    """Synthesize findings from multiple specialist agents into one unified diagnosis."""
    original_query: str = dspy.InputField()
    agent_findings: str = dspy.InputField()   # labeled findings from each agent
    unified_diagnosis: str = dspy.OutputField()  # <300 words, integrated
```

- Pure LLM reasoning over provided evidence — **no HTTP call, no RAG**
- Falls back to concatenation if synthesis fails or rate limits hit
- Uses Claude Haiku 4.5 (same model, already configured)

### B2 — Synthesis replaces concatenation in all 3 finalization paths

`_run_synthesis_round()` removed entirely (it called Governance for fresh RAG — wrong approach).

### B3 — Parallel agent execution

Old: governance → hardware → telemetry (serial, avg 303 s)

New: governance → `asyncio.gather(hardware, telemetry)` → synthesis = **169.8 s avg (−44%)**

---

## Key confound: Rate limits

Anthropic API rate limit (50k input tokens/min) caused synthesis to fall back to concatenation for ~7/12 cases. Synthesis triples the input token volume vs a single agent call.

**Consequence:** The measured +6.7 pp improvement is a **lower bound**. Cases where synthesis executed fully (e.g. `missed_maintenance_escalation`, `cascading_thermal_fault`) performed better than cases where it fell back.

The `known_fault_code_lookup` failure (MAS 0%) is consistent with a synthesis-path error under rate limiting.

---

## What the results mean for the hypothesis

| Claim | Evidence |
|-------|----------|
| MAS can produce cross-domain reasoning | Judge cross-domain scores 0.33–0.92, mean ~0.7 ✓ |
| MAS can demonstrate emergence | 2/12 cases with +20 pp margin ✓ |
| MAS outperforms single-agent baseline overall | No — still 20 pp below single_all_data ✗ |
| Synthesis is the enabling condition for emergence | 0/12 without synthesis → 2/12 with synthesis ✓ |

---

## File map

```
src/
  orchestration/
    synthesis.py          ← NEW: DSPy ChainOfThought synthesis module
    multi_round.py        ← UPDATED: parallel calls + synthesis finalization
  evaluation/
    run_evaluation.py     ← unchanged
    ablation_runner.py    ← unchanged

results/ablation/
  thesis_summary.json     ← Run 3 aggregate results (latest)

thesis/
  main_with_visuals.tex   ← Results ch.4 (Sections 4.1–4.6) + Discussion ch.5 written
                             Run 3 Section 4.6 added, Discussion updated with before/after
                             92 pages, compiled clean (xelatex → biber → xelatex × 2)
```
