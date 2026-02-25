# Agentic Infra Copilot — Current State & Results
**Date:** 2026-02-25 | **Status:** Run 2 complete, Run 3 ready to execute

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

**5-mode ablation** across **12 test cases** (4 simple / 4 moderate / 4 complex) = **60 evaluations per run**.

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

## Run 1 → Run 2: what broke and what was fixed (1 min)

**Run 1 (23 Feb)** — found 3 infrastructure bugs that invalidated results:
1. Payload extraction: orchestrator read from `findings` key; agents used `contextual_explanation`, `root_cause`, etc. → empty responses
2. Keyword mapping: expected keywords undefined for some modes → scorer errors
3. Baseline routing: `single_all_data` mode still delegated to specialists → indistinguishable from MAS

**Run 2 (24 Feb)** — all bugs fixed, all 60 evaluations completed, zero timeouts.

---

## Run 2 results (2 min)

### Per-mode aggregate scores

| Mode | Keyword Acc | Judge Score | Semantic Sim | Avg Latency |
|------|-------------|-------------|--------------|-------------|
| Governance Only | 48.3% | 66.9% | 54.5% | 97.9 s |
| Hardware Only | 73.3% | 78.2% | 68.3% | 16.7 s |
| Telemetry Only | 53.3% | 41.3% | 41.0% | 13.9 s |
| **Single + All Data** | **81.7%** | **87.8%** | **70.5%** | 87.5 s |
| Full MAS | 58.3% | 69.4% | 49.8% | 303.4 s |

**Headline:** single agent with all data beats the MAS by **23.4 percentage points** on keyword accuracy.

### Emergence: 0 / 12

| Difficulty | Mean emergence margin |
|------------|----------------------|
| Simple | −30% |
| Moderate | −24% |
| Complex | −24% |

All negative. No test case showed MAS outperforming the best single agent.

### Latency
- MAS: **303.4 s** vs baseline: **87.5 s** → **+247% overhead**
- MAS sequential: governance → hardware → telemetry (serial HTTP calls)
- Agent consultation: Governance 12/12, Hardware 11/12, Telemetry 9/12
- Worst case: `missed_maintenance_escalation` — MAS 524 s vs single 92 s

---

## The key finding: it's not the reasoning, it's the assembly (2 min)

Despite low accuracy scores, MAS **judge cross-domain scores ranged 0.33–0.92 (mean ≈ 0.70)**.

This is the critical dissociation:
- Agents **do** produce cross-domain reasoning (hardware refs in governance output, SLA refs in hardware output)
- But the final MAS output is **concatenated** — `governance_agent: [...] hardware_agent: [...] telemetry_agent: [...]`
- This dilutes keyword density, introduces competing framings, and confuses the scorer

**Best case — `cascading_thermal_fault`:** MAS produced 6-point cross-domain analysis (equipment age, duty cycles, maintenance gaps, software cascades, hub pressure, SLA mismatch). Judge cross-domain score: 0.92. But keyword accuracy = 80%, same as single agent — no positive margin.

**Worst case — `phantom_load_spike`:** Single agent 100%, MAS 40%. Hardware said sensor drift, Telemetry said scheduling artifacts — contradictory, unresolved.

**Root cause:** The existing `_run_synthesis_round()` called Governance for synthesis, but Governance ran fresh RAG instead of integrating the provided findings. It was a 4th independent agent call, not a synthesis step.

---

## What was fixed for Run 3 (2 min)

### B1 — New DSPy synthesis module (`src/orchestration/synthesis.py`)

```python
class SynthesizeDiagnosis(dspy.Signature):
    """Synthesize findings from multiple specialist agents into one unified diagnosis."""
    original_query: str = dspy.InputField()
    agent_findings: str = dspy.InputField()   # labeled findings from each agent
    unified_diagnosis: str = dspy.OutputField()  # <300 words, integrated
```

- Pure LLM reasoning over provided evidence — **no HTTP call, no RAG**
- Falls back to concatenation if synthesis fails
- Uses Claude Haiku 4.5 (same model, already configured)

### B2 — Synthesis replaces concatenation in all 3 finalization paths

Old:
```python
findings.append(f"{resp.agent_id}: {resp.findings}")
session.final_diagnosis = "\n".join(findings)
```

New (all three methods: `_finalize_diagnosis`, `_synthesize_partial_findings`, `_synthesize_best_effort`):
```python
findings_dict = self._collect_findings(session)
session.final_diagnosis = self.synthesizer.synthesize(query, findings_dict)
```

`_run_synthesis_round()` removed entirely.

### B3 — Parallel agent execution

Old: governance → hardware → telemetry (serial, ~303 s)

New: governance → `asyncio.gather(hardware, telemetry)` → synthesis

Theoretical latency: `t_gov + max(t_hw, t_tel) + t_synth` instead of `t_gov + t_hw + t_tel`
Expected reduction: **~100–120 s off MAS average** (from 303 → ~180 s)

---

## Expected Run 3 outcomes (1 min)

| Metric | Run 2 (MAS) | Run 3 target | Mechanism |
|--------|-------------|--------------|-----------|
| Keyword accuracy | 58.3% | ≥ 75% | Synthesis concentrates keywords |
| Judge score | 69.4% | ≥ 80% | No competing framings |
| Latency | 303 s | ~150–200 s | Parallel hw+tel calls |
| Emergence | 0/12 | ≥ 1/12 | Synthesis surfaces buried cross-domain keywords |

If emergence remains 0/12 after synthesis, the investigation shifts to whether keyword accuracy is the right proxy for cross-domain diagnostic quality — the judge cross-domain scores already suggest the agents reason better than the metric captures.

---

## How to run (30 sec)

```bash
# Verify synthesis import
python -c "from src.orchestration.synthesis import DiagnosisSynthesizer; print('OK')"

# Check agents are healthy
python -m src.evaluation.run_evaluation --dry-run

# Single test case smoke test
python -m src.evaluation.run_evaluation --test-case cascading_thermal_fault --no-resume

# Full Run 3 (60 evaluations)
python -m src.evaluation.run_evaluation --no-resume
```

Results land in `results/ablation/thesis_summary.json`. Compare Run 2 vs Run 3 to quantify synthesis impact.

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
    judge.py              ← unchanged

results/ablation/
  thesis_summary.json     ← Run 2 aggregate results
  [per-test-case files]   ← 12 individual breakdowns

thesis/
  main_with_visuals.tex   ← Results ch.4 + Discussion ch.5 written
                             4 pgfplots figures, 3 tables, 86 pages compiled clean
```
