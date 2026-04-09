# Evaluation Process Log — Agentic Infra Co-Pilot

**Thesis:** Domain-agnostic critical infrastructure diagnostics via multi-agent emergence  
**Programme:** AISS Master's Programme  
**Validation partner:** Siemens Healthineers  
**Last updated:** 2026-04-09

---

## Purpose of This Document

This document provides a complete audit trail of every evaluation run, every bug discovered, every code change made, and the engineering reasoning behind each decision. It is intended to support reproducibility, serve as an appendix reference in the thesis, and provide complete transparency about how the final evaluation results were obtained.

---

## 1. System Overview

### 1.1 Architecture

The system under evaluation is a **tripartite Multi-Agent System (MAS)** for MRI infrastructure fault diagnosis. Three specialist agents—each an independent FastAPI microservice—collaborate through a multi-round orchestration protocol to produce emergent cross-domain diagnoses.

| Agent | Port | Domain | Knowledge Base Size |
|-------|------|---------|---------------------|
| Governance Agent | 8001 | SLA compliance, uptime targets, institutional policy, clinical protocols | 418 documents |
| Hardware Agent | 8002 | MRI hardware errors, DICOM conformance, thermal management, Siemens Phoenix Protocol | 9,853 documents (MAGNETOM operator manuals + safety PDFs added before Run 3) |
| Telemetry Agent | 8003 | MRI event logs, session monitoring, temporal fault patterns, safety zones | 945 documents |

Each agent uses:
- **ChromaDB** — domain-specific vector store for RAG retrieval  
- **sentence-transformers** (`all-MiniLM-L6-v2`) — query and document embeddings  
- **DSPy ChainOfThought** — structured LLM prompting with typed input/output fields  
- **FastAPI + Uvicorn** — HTTP microservice interface

### 1.2 Three-Tier Model Strategy

Three LLMs are used across the system, selected to balance cost, capability, and rate limits:

| Tier | Model | Role |
|------|-------|------|
| **Router** | Azure OpenAI GPT-4.1 (`openai/gpt-4.1`) | Request classification, delegation routing, intent detection |
| **Reasoner** | Anthropic Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) | Agent domain reasoning (all three agents), LLM-as-Judge scoring |
| **Synthesiser** | Anthropic Claude Sonnet 4.6 (`claude-sonnet-4-6`) | Final cross-domain synthesis in MAS mode |

The separation of routing from reasoning reduces per-call cost and allows the cheaper Azure GPT-4.1 to handle classification decisions while reserving Sonnet/Haiku for substantive reasoning.

### 1.3 Autonomy Protocol

Before answering any query, each agent evaluates the request and returns one of six response types that govern orchestration behaviour:

| Response Type | Meaning | Orchestrator Action |
|---------------|---------|---------------------|
| `ANSWER` | Complete, confident response | Finalise if confidence ≥ 0.5 (ablation threshold); else consult remaining agents |
| `PARTIAL` | Incomplete — more context needed | Call remaining unconsulted agents in parallel |
| `CONSULT` | Wants a specific peer agent's input | Call suggested agent plus remaining unconsulted agents in parallel |
| `REDIRECT` | Wrong agent for this query | Route to suggested agent plus remaining |
| `CLARIFY` | Needs user information | Surface clarification questions |
| `REFUSE` | Cannot answer | Try remaining agents |

This protocol prevents hallucination cascades and creates measurable routing signals for evaluation.

### 1.4 DSPy Signatures

Each agent uses domain-specific DSPy `ChainOfThought` signatures. The key signatures are:

**Governance Agent:**
- `ProfileInstitution` — institutional context, operational risk (symptom queries)
- `AnalyzeWorkloadPattern` — workload assessment (workload queries)
- `ExplainErrorContext` — error operational context
- `DelegateToSpecialist` — routing to hardware/telemetry agents
- `IntegrateFindings` — multi-agent synthesis
- `AnswerGeneralQuery` — general knowledge queries
- `EvaluateRequest` — query classification and confidence assessment (uses router LM)

**Hardware Agent:**
- `AnalyzeHardwareError` — DICOM/hardware fault diagnosis
- `DiagnoseDICOMFailure` — DICOM conformance failures
- `LookupTechnicalSpec` — specification retrieval
- `EvaluateRequest` — (same pattern, uses router LM)

**Telemetry Agent:**
- `ValidateComplianceSOP` — SOP compliance checking
- `ReviewDiagnosticAction` — action safety review
- `CheckSafetyZone` — zone classification
- `AuditWorkflow` — workflow audit
- `EvaluateRequest` — (same pattern, uses router LM)

### 1.5 Evaluation Framework

**Ablation design:** Every test case is run in five modes to isolate the effect of data access versus agent collaboration:

| Mode | Agents Active | Data Access | Purpose |
|------|--------------|-------------|---------|
| `governance_only` | Governance only | Governance store | Single-domain ceiling |
| `hardware_only` | Hardware only | Hardware store | Single-domain ceiling |
| `telemetry_only` | Telemetry only | Telemetry store | Single-domain ceiling |
| `single_all_data` | Governance only | All three stores merged | Critical baseline — isolates collaboration value from data access |
| `mas_full` | All three agents | Domain-specific stores | System under test |

**Test suite:** 12 `EmergenceTestCase` instances across three difficulty levels:

| Difficulty | Count | Characteristic |
|-----------|-------|----------------|
| Simple | 2 | Single-domain fault, one expected agent |
| Moderate | 5 | Two-domain fault, consultation expected |
| Complex | 5 | Three-domain fault, full MAS required |

Test cases: `cascading_thermal_fault`, `phantom_load_spike`, `gradient_coil_degradation`, `helium_boiloff_cascade`, `shimming_environmental`, `multi_scanner_cooling`, `software_update_regression`, `rf_amplifier_intermittent`, `network_false_alarm`, `protocol_conflict_sla`, `missed_maintenance_escalation`, `known_fault_code_lookup`.

**Scoring instruments:** Four complementary measures per evaluation:

| Instrument | Method | What it Captures |
|-----------|--------|-----------------|
| Keyword accuracy | Ground-truth keyword matching | Diagnostic precision (primary metric) |
| LLM-as-Judge (4D) | Claude Haiku scores accuracy, relevance, completeness, cross_domain (0–1 each) | Qualitative response quality |
| Semantic similarity | Sentence-transformer cosine vs reference diagnosis | Meaning-level fidelity |
| Latency | Wall-clock time per evaluation | Orchestration overhead |

**Emergence criterion:** Emergence is demonstrated when *both* conditions hold:
1. MAS keyword accuracy > best single-agent keyword accuracy across all four non-MAS modes (positive emergence margin)
2. MAS response contains ≥ 1 explicit cross-domain reference — OR — LLM-as-Judge cross_domain score > 0.5

The dual criterion prevents false negatives from fragile keyword detection.

**Total evaluations per run:** 12 test cases × 5 modes = **60 evaluations**

---

## 2. Evaluation Run History

### Run 1 — Infrastructure Discovery Run (2026-02-23)

**Status:** ❌ Discarded — three infrastructure bugs identified

**Purpose:** First full execution of the ablation framework.

**Bugs discovered:**

| Bug | Description | Impact |
|-----|-------------|--------|
| B1: Payload extraction failure | `multi_round.py` only extracted `contextual_explanation` from agent responses; other agents use `root_cause`, `diagnosis`, `answer` etc. | MAS findings were empty for most cases |
| B2: Keyword mapping error | Ground-truth keyword list had normalisation mismatch | All accuracy scores artificially low |
| B3: Baseline routing broken | `single_all_data` mode did not correctly pass combined context to governance agent | Baseline was not comparable to MAS |

**Outcome:** Results discarded. All three bugs fixed before Run 2.

---

### Run 2 — First Complete Run (2026-02-24)

**Status:** ✅ Complete — 60/60 evaluations, zero timeouts

**Key finding:** MAS significantly underperformed the single-agent baseline.

**Aggregate results:**

| Mode | Keyword Acc | Judge Score | Semantic Sim | Avg Latency |
|------|:-----------:|:-----------:|:------------:|:-----------:|
| Governance Only | 48.3% | 66.9% | 54.5% | 97.9 s |
| Hardware Only | 73.3% | 78.2% | 68.3% | 16.7 s |
| Telemetry Only | 53.3% | 41.3% | 41.0% | 13.9 s |
| **Single + All Data** | **81.7%** | **87.8%** | **70.5%** | 87.5 s |
| Full MAS | 58.3% | 69.4% | 49.8% | 303.4 s |

**Emergence:** 0/12 test cases demonstrated emergence. All emergence margins were negative.

| Difficulty | MAS avg | Best single avg | Emergence margin |
|-----------|---------|-----------------|:----------------:|
| Simple | 30% | 60% | **−30%** |
| Moderate | 64% | 88% | **−24%** |
| Complex | 64% | 88% | **−24%** |

**Latency:** MAS average 303.4 s vs single_all_data 87.5 s = +215.9 s overhead (+247%).

**Root cause diagnosis — the synthesis gap:**

Despite high LLM-as-Judge cross-domain scores (0.33–0.92, mean ≈ 0.70), keyword accuracy was poor. Investigation revealed that the `_run_synthesis_round()` method — which was supposed to integrate findings — actually re-called the Governance Agent to produce a *fourth independent agent response*. The governance agent ran fresh RAG retrieval against its vector store instead of reasoning over the provided evidence.

All three finalisation methods (`_finalize_diagnosis`, `_synthesize_partial_findings`, `_synthesize_best_effort`) concatenated agent outputs with agent-name prefixes (`governance_agent: [...] hardware_agent: [...]`) rather than synthesising them. This diluted keyword density and introduced competing framings with no resolution step.

**Fixes implemented before Run 3:**

**Fix A — DSPy Synthesis Module (`src/orchestration/synthesis.py`)**

A new `DiagnosisSynthesizer` class using a dedicated DSPy `ChainOfThought` signature replaces the governance-agent-based synthesis. Pure LLM reasoning over the provided `findings_dict` — no HTTP call, no RAG retrieval. Falls back to concatenation on synthesis failure.

```python
class SynthesizeDiagnosis(dspy.Signature):
    """Synthesize findings from multiple specialist agents into one unified diagnosis."""
    original_query: str = dspy.InputField(...)
    agent_findings: str = dspy.InputField(desc="Labeled findings from each specialist agent")
    unified_diagnosis: str = dspy.OutputField(
        desc="Concise integrated root-cause diagnosis with cross-domain connections "
             "and recommended actions in under 300 words"
    )
```

Uses Claude Sonnet 4.6 for synthesis (higher capability than Haiku for integration tasks).

**Fix B — Parallel Agent Execution (`src/orchestration/multi_round.py`)**

Added `_call_agents_parallel()` using `asyncio.gather()`. Hardware and Telemetry operate on non-overlapping knowledge domains, making their analyses independent and safe to parallelise. Expected latency reduction: ~100–120 s off MAS average.

```python
async def _call_agents_parallel(self, agent_ids, query, context, ...):
    tasks = [self._call_agent(aid, query, context) for aid in agent_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # exceptions → REFUSE responses, not crashes
```

**Fix C — Context Injection Parity (`src/evaluation/ablation_runner.py`)**

MAS mode was only passing `governance_context` in the query, while `single_all_data` was passing all three domain contexts. This gave MAS agents less information than the baseline, introducing a confound. Fixed by including all three contexts in the MAS query:

```python
session = await self.orchestrator.run_diagnosis(
    query=(
        f"{test_case.description}\n\n"
        f"Governance context: {test_case.governance_context}\n\n"
        f"Hardware context: {test_case.hardware_context}\n\n"
        f"Telemetry context: {test_case.telemetry_context}\n\n"
        f"IMPORTANT: This scenario requires cross-domain analysis. "
        f"Consult hardware and telemetry specialists — they hold data "
        f"not available in governance records."
    ),
```

**Fix D — Increased Inter-Mode Delay (`src/evaluation/ablation_runner.py`)**

The inter-mode delay between the five evaluation modes for each test case was increased from 10 s to 30 s. The 10 s gap was insufficient: hardware and telemetry agents, which use Haiku with a tight token budget, hit HTTP 429 rate-limit errors immediately after governance had consumed the per-minute token budget. At 10 s, the Anthropic token window had not sufficiently reset.

---

### Run 3 — Context-Parity and Participation Remediation (2026-04-08, attempt 1)

**Status:** ❌ Partially invalid — hardware and telemetry agents were not running during evaluation

**Hardware/Telemetry accuracy:** 0% across all 12 test cases for both agents

**Symptom pattern:** Both hardware_only and telemetry_only modes returned 0% accuracy with ~155 s latency per evaluation. The 155 s total matched the retry exhaustion pattern: `RETRY_DELAYS = [20, 45, 90]` seconds = 155 s total before final failure.

**Root cause:** The Docker containers for hardware and telemetry agents were not running at the time of evaluation. The pre-flight health check only queried `/health` endpoints, which are served by the FastAPI application even when the DSPy components are still initialising or the vector store is not yet populated. The governance agent's health check passed because it was already warmed up.

**Investigation method:** The pattern was identified by correlating the per-case latency (~155 s) with the sum of retry delays in `multi_round.py`. A 155 s total across all test cases — identically, for both hardware and telemetry, independently — was statistically impossible under random failure. The sum `20 + 45 + 90 = 155` s matched precisely.

**Fix E — Live Consult Probe in Preflight (`src/evaluation/run_evaluation.py`)**

The preflight check was extended with a `probe_agent_consult()` function that sends an actual `/consult` request to each agent (not just `/health`), verifying end-to-end DSPy processing:

```python
async def probe_agent_consult(name: str, url: str) -> bool:
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
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{url}/consult", json={"card": card.model_dump(), "await_response": True})
        return resp.status_code == 200
```

The 120 s timeout accommodates DSPy cold-start initialisation (loading models, warming up the embedding pipeline). The preflight now fails the run if either `/health` OR the `/consult` probe fails for any agent.

**Fix F — Increased Between-Case Delay**

`DELAY_BETWEEN_CASES_S` increased from 2 s to 45 s to allow rate-limit windows to reset between test cases in addition to the per-mode 30 s inter-mode delay.

---

### Run 4 — First Participatory Run (2026-04-08, attempt 2)

**Status:** ✅ All 60 evaluations completed. Hardware and telemetry agents now active.

**All three agents confirmed running via Docker compose before evaluation start.**

**Aggregate results:**

| Mode | Keyword Acc | Judge Score | Semantic Sim | Avg Latency |
|------|:-----------:|:-----------:|:------------:|:-----------:|
| Governance Only | 33.3% | 43.2% | 5.6% | 109.8 s |
| Hardware Only | 43.3% | 41.0% | 7.8% | 15.2 s |
| Telemetry Only | 36.7% | 41.5% | 4.5% | 15.0 s |
| **Single + All Data** | **50.0%** | **47.9%** | **6.1%** | 79.2 s |
| Full MAS | **53.3%** | **55.5%** | **3.3%** | 102.2 s |

**Emergence results:**

| Metric | Value |
|--------|-------|
| Cases with emergence | 2 / 12 (16.7%) |
| Cases with positive margin | 2 / 12 |
| MAS beats best single on complex cases | avg +8% margin |

**Demonstrated emergence cases:**

| Test Case | Difficulty | MAS Acc | Best Single | Margin | Cross-Domain Refs |
|-----------|-----------|---------|-------------|--------|:-----------------:|
| `gradient_coil_degradation` | complex | 80% | 60% | **+20%** | 6 |
| `helium_boiloff_cascade` | complex | 100% | 80% | **+20%** | 8 |

**Run 4 per-case accuracy breakdown:**

| Test Case | Difficulty | Gov | Hw | Tel | SAD | MAS |
|-----------|-----------|-----|-----|-----|-----|-----|
| cascading_thermal_fault | complex | 80% | 80% | 80% | 80% | 80% |
| phantom_load_spike | moderate | 20% | 60% | 60% | 100% | 100% |
| gradient_coil_degradation | complex | 40% | 60% | 60% | 60% | **80%** |
| helium_boiloff_cascade | complex | 40% | 80% | 60% | 80% | **100%** |
| shimming_environmental | complex | 40% | 80% | 40% | 100% | 100% |
| multi_scanner_cooling | complex | 80% | 100% | 60% | 100% | 100% |
| software_update_regression | moderate | 40% | 60% | 80% | 80% | 80% |
| rf_amplifier_intermittent | moderate | 60% | **0%** | **0%** | **0%** | **0%** |
| network_false_alarm | simple | **0%** | **0%** | **0%** | **0%** | **0%** |
| protocol_conflict_sla | moderate | **0%** | **0%** | **0%** | **0%** | **0%** |
| missed_maintenance_escalation | moderate | **0%** | **0%** | **0%** | **0%** | **0%** |
| known_fault_code_lookup | simple | **0%** | **0%** | **0%** | **0%** | **0%** |

*SAD = Single All Data. Bold zeros indicate failing cases.*

**5 consistently-failing test cases:** `network_false_alarm`, `protocol_conflict_sla`, `rf_amplifier_intermittent` (hw/tel/SAD/MAS), `missed_maintenance_escalation`, `known_fault_code_lookup`.

**MAS response distribution:** All three agents consulted in 12/12 cases (governance 100%, hardware 100%, telemetry 100%). Average rounds: 1.0.

**Latency analysis (Run 4):**

| Test Case | MAS Latency | Single All Data | Overhead |
|-----------|:-----------:|:---------------:|:--------:|
| cascading_thermal_fault | 121.3 s | 79.6 s | +41.6 s |
| phantom_load_spike | 115.8 s | 53.9 s | +61.9 s |
| gradient_coil_degradation | 160.2 s | 89.5 s | +70.7 s |
| helium_boiloff_cascade | 161.9 s | 146.1 s | +15.7 s |
| shimming_environmental | 172.7 s | 65.8 s | +106.9 s |
| multi_scanner_cooling | 144.9 s | 108.6 s | +36.3 s |
| software_update_regression | 132.6 s | 115.6 s | +17.0 s |
| rf_amplifier_intermittent | 47.4 s | 57.4 s | **−10.0 s** |
| network_false_alarm | 43.2 s | 54.4 s | **−11.1 s** |
| protocol_conflict_sla | 44.8 s | 63.5 s | **−18.7 s** |
| missed_maintenance_escalation | 43.5 s | 56.4 s | **−12.8 s** |
| known_fault_code_lookup | 38.1 s | 59.2 s | **−21.1 s** |

**Note on negative MAS overhead:** The 5 failing cases show *negative* MAS overhead. This is because MAS terminated early (governance returned empty findings, and the short synthesis path was faster than governance's heavier single_all_data processing). This is further evidence of the DSPy parsing failures affecting these cases.

---

### Run 4 Post-Analysis — DSPy None Output Failure Investigation

**Problem:** 5 test cases (plus partial failure on `rf_amplifier_intermittent`) returned 0% accuracy across all modes. The symptom was `findings = "No findings from {agent}"` in the ablation runner logs.

**Root cause investigation path:**

**Step 1 — Eliminate rate limiting.** The failing cases had 17–21 s latency per mode, not the 155 s retry exhaustion pattern. This ruled out rate limiting.

**Step 2 — Examine `multi_round.py` findings extraction.** The findings extractor checked only four payload keys:

```python
findings = (
    payload.get('contextual_explanation')
    or payload.get('root_cause')
    or payload.get('diagnosis')
    or payload.get('answer')
    or ''
)
```

For symptom-type queries, governance builds a response payload containing `contextual_explanation`, `institution_profile`, `risk_factors`, and `recommended_actions`. There is no `answer` key in symptom payloads. If `contextual_explanation` was None, all four checks failed and `findings = ''`.

**Step 3 — Trace the None origin.** In all three agents' `main.py`, response payload values were set using:

```python
"contextual_explanation": getattr(result, 'contextual_explanation', ''),
```

Python's `getattr(obj, name, default)` returns the `default` only when the attribute does **not exist** on the object. When DSPy creates a `dspy.Prediction` object, it sets *all* output fields as attributes — even when the LLM output could not be parsed into a field's expected value. In that case, the attribute exists but its value is `None`. Therefore `getattr(result, 'contextual_explanation', '')` returns `None` (not `''`), and `payload.get('contextual_explanation')` = `None` — falsy — causing the findings chain to fail.

**Step 4 — Identify the full set of bugs.** A systematic search found five distinct bugs:

---

## 3. Complete Bug Catalogue and Fixes (Pre-Run 5)

### Bug 1 — `getattr` None Leakage (All Three Agents)

**File:** `src/agents/{governance,hardware,telemetry}_agent/main.py`

**Manifestation:** Agent response payload contains `None` values for string fields when DSPy Prediction has a field set to `None`.

**Root cause:** `getattr(result, field, default)` returns `None` (not `default`) when the attribute exists but is `None`. DSPy always sets all output field attributes on a Prediction object, even for unparseable fields.

**Fix:**

```python
# Before (all three agents, all response_payload getattr calls)
"contextual_explanation": getattr(result, 'contextual_explanation', ''),

# After
"contextual_explanation": getattr(result, 'contextual_explanation', '') or '',
```

Every string field in every `response_payload` block in all three agents' `main.py` files was updated. Non-string defaults (e.g., `'Unknown'`, `'None identified'`, `'No immediate actions'`) were also updated:

```python
"institution_profile": getattr(result, 'institution_profile', 'Unknown') or 'Unknown',
"risk_factors": getattr(result, 'risk_factors', 'None identified') or 'None identified',
"recommended_actions": getattr(result, 'recommended_actions', 'No immediate actions') or 'No immediate actions',
```

**Also fixed:** Delegation fields in governance agent that are passed to `delegate_to_specialist()`:

```python
target_agent = getattr(result, 'target_agent', 'self') or 'self'
delegation_reason = getattr(result, 'delegation_reason', '') or ''
refined_query = getattr(result, 'refined_query', query) or query
```

Without this, `refined_query = None` would be passed as the query string to a downstream HTTP call, causing a serialisation error.

---

### Bug 2 — `float(None)` TypeError on Confidence Extraction (All Three Agents)

**File:** `src/agents/{governance,hardware,telemetry}_agent/main.py`

**Manifestation:** Potential `TypeError` crash on the `eval_confidence` extraction line when DSPy's `EvaluateRequest` signature returns `None` for `confidence_level`.

**Root cause:** Same `getattr` None pattern, but applied to a numeric field and then cast directly with `float()`:

```python
# Before
eval_confidence = float(getattr(evaluation, 'confidence_level', getattr(evaluation, 'confidence', 0.8)))
```

If `evaluation.confidence_level` exists but is `None`, `getattr` returns `None`, and `float(None)` raises `TypeError`. The nesting of `getattr` calls inside `float()` makes the error invisible — the inner `getattr` fallback never triggers because the outer attribute exists.

**Fix:**

```python
# After (all three agents, identical pattern)
_raw_conf = getattr(evaluation, 'confidence_level', None) or getattr(evaluation, 'confidence', None)
try:
    eval_confidence = float(_raw_conf) if _raw_conf is not None else 0.8
except (TypeError, ValueError):
    eval_confidence = 0.8
```

The fallback of `0.8` is intentional: if the router LLM cannot express a confidence level, defaulting to high confidence allows the orchestration to proceed rather than blocking the entire evaluation run.

---

### Bug 3 — Narrow Findings Extraction in Orchestrator

**File:** `src/orchestration/multi_round.py`

**Manifestation:** Findings extracted as empty string even when agent payload contains non-empty fields under different key names.

**Root cause:** The four-field extraction chain did not cover the full set of response payload keys used across all three agents and all query types:

| Agent | Query Type | Primary Payload Key |
|-------|-----------|---------------------|
| Governance | symptom | `contextual_explanation` |
| Governance | workload | `workload_assessment` |
| Governance | general | `answer` |
| Governance | (integrated) | `root_cause` (added by `integrate_specialist_response`) |
| Hardware | dicom_diagnosis / hardware_error | `diagnosis` |
| Hardware | technical_spec / general | `answer` |
| Telemetry | compliance_check | `compliance_details` |
| Telemetry | action_review | `safety_assessment`, `sop_compliance` |
| Telemetry | safety_zone | `zone_classification` |
| Telemetry | workflow_audit | `audit_result`, `safety_gaps` |

**Fix:** Expanded to check all 14 known payload keys across all three agents and all query types:

```python
findings = (
    payload.get('contextual_explanation')
    or payload.get('root_cause')
    or payload.get('diagnosis')
    or payload.get('answer')
    or payload.get('risk_factors')
    or payload.get('recommended_actions')
    or payload.get('workload_assessment')
    or payload.get('compliance_details')
    or payload.get('safety_assessment')
    or payload.get('sop_compliance')
    or payload.get('zone_classification')
    or payload.get('audit_result')
    or payload.get('safety_gaps')
    or payload.get('institution_profile')
    or ''
) or ''
```

The trailing `or ''` guards against the edge case where the entire chain evaluates to `None` due to an unexpected payload structure.

---

### Bug 4 — Fallback String Masking in Findings Extraction

**File:** `src/orchestration/multi_round.py`

**Manifestation:** After Bug 1 fix, agent `getattr` defaults (`'Unknown'`, `'None identified'`, `'No immediate actions'`) are truthy strings. The `or`-chain stops at the first truthy value, meaning `institution_profile = 'Unknown'` could terminate the chain before reaching `risk_factors` which might contain real DSPy-generated content.

**Root cause:** Python's `or`-chain treats any non-empty, non-`None` string as truthy. Agent fallback defaults like `'Unknown'` are non-empty strings. If DSPy fails to parse `contextual_explanation` (returns `None` → `''` after Bug 1 fix) but successfully parses `risk_factors` (returns real text), the chain should reach `risk_factors`. But if `institution_profile` is checked first and contains `'Unknown'`, the chain terminates prematurely with useless content.

**Fix:** Added a `_real()` helper that filters out known fallback strings before the `or`-chain evaluation, and reordered `institution_profile` to last position (as the weakest fallback):

```python
_FALLBACK_STRS = {
    'unknown', 'none identified', 'no immediate actions',
    'unable to determine', 'unable to process query',
    'unable to find specification', 'needs-review',
}

def _real(v):
    """Return v if it contains real content, else None."""
    if not v:
        return None
    if str(v).strip().lower() in _FALLBACK_STRS:
        return None
    return v

findings = (
    _real(payload.get('contextual_explanation'))
    or _real(payload.get('root_cause'))
    or _real(payload.get('diagnosis'))
    or _real(payload.get('answer'))
    or _real(payload.get('risk_factors'))
    # ... (all fields via _real())
    or _real(payload.get('institution_profile'))  # last — weakest signal
    or ''
) or ''
```

This ensures `findings = ''` when ALL DSPy fields are fallback-only, rather than misleadingly returning `'Unknown'` as the agent's contribution.

---

### Bug 5 — `_is_empty_response` Incomplete Check

**File:** `src/evaluation/ablation_runner.py`

**Manifestation:** In `single_all_data` mode, governance agent returns either `"No findings from governance_agent"` (pre-Bug 3 fix) or one of the agent fallback strings (`'Unknown'`, etc., pre-Bug 4 fix). The `_is_empty_response()` method did not recognise these as empty, causing `single_all_data` to accept a useless governance response rather than falling through to try hardware or telemetry.

**Root cause:** The original check only covered a small set of known empty responses:

```python
def _is_empty_response(self, text: str) -> bool:
    if not text:
        return True
    stripped = text.strip().lower()
    return stripped in ("", "no findings", "no findings.", "error", "n/a") or stripped.startswith("error:")
```

Neither `"no findings from governance_agent"` nor `"unknown"` nor `"no immediate actions"` were in the set.

**Fix:** Extended the check to include all agent fallback strings and the `"no findings from"` prefix:

```python
def _is_empty_response(self, text: str) -> bool:
    if not text:
        return True
    stripped = text.strip().lower()
    if stripped in ("", "no findings", "no findings.", "error", "n/a"):
        return True
    if stripped.startswith("error:") or stripped.startswith("no findings from"):
        return True
    fallback_strings = {
        "unknown", "none identified", "no immediate actions",
        "unable to determine", "unable to process query",
        "unable to find specification", "needs-review",
    }
    return stripped in fallback_strings
```

With this fix, `single_all_data` mode correctly falls through from governance to hardware to telemetry when governance produces only fallback content, giving hardware and telemetry agents the opportunity to provide real findings for hardware-domain queries.

---

## 4. Code Change Summary

| Commit | Files | Change |
|--------|-------|--------|
| `1d41663` | `run_evaluation.py`, `ablation_runner.py` | Live consult probe, inter-mode delay 10→30 s |
| `db7aeff` | `ablation_runner.py` | Context injection parity fix |
| `ad30962` | `main.py` (×3), `multi_round.py`, `ablation_runner.py` | Full DSPy None hardening (Bugs 1–5) |

All changes are on the `dev` branch. The `main` branch reflects the stable pre-Run-3 state.

---

## 5. Expected Outcomes — Run 5

Run 5 is the thesis final evaluation run. Expected improvements from the Bug 1–5 fixes:

**For the 5 previously-failing cases (`network_false_alarm`, `protocol_conflict_sla`, `rf_amplifier_intermittent`, `missed_maintenance_escalation`, `known_fault_code_lookup`):**

- Hardware_only and telemetry_only modes: will now receive real diagnostic output if DSPy produces any non-None field across the expanded 14-key chain
- Single_all_data mode: will now correctly fall through to hardware/telemetry agents when governance returns only fallback strings
- MAS mode: synthesis will receive real hardware/telemetry findings rather than empty governance contribution

**Conservative projection (assuming DSPy still fails for all 5 cases):**
- Hardware_only: remains 0% for the 5 cases (DSPy still returns all-None)
- Single_all_data: may improve as hardware agent is tried for hardware-domain queries
- MAS mode: may improve as synthesis proceeds over hardware/telemetry data even with empty governance

**Optimistic projection (DSPy partially recovers for these cases):**
- Hardware_only for `rf_amplifier_intermittent`: should improve significantly — governance already scored 60% on this case, meaning the query is answerable; the fix allows hardware's alternative fields to surface
- `single_all_data` for all 5 cases: should improve as the agent fallthrough logic now correctly redirects to hardware

**Emergence:** Run 4 demonstrated 2/12 emergence cases (both complex). If Run 5 repairs the 5 failing cases (all simple/moderate), the overall accuracy metrics will shift but the emergence pattern should be preserved or strengthened.

---

## 6. Preflight Checklist for Run 5

Before starting Run 5, the following must be confirmed:

```bash
# 1. Confirm all three Docker containers are running
docker ps | grep agentic-infra

# 2. Wait for agents to warm up (DSPy cold-start ~60-90s per agent)
# Then run dry-run — all three agents must pass BOTH health AND consult probe
python -m src.evaluation.run_evaluation --dry-run

# 3. Clear previous Run 4 results
rm -f results/ablation/*_ablation.json results/ablation/thesis_summary.json

# 4. Start evaluation
python -m src.evaluation.run_evaluation
```

Expected dry-run output (all agents passing):
```
✓ governance_agent  status=healthy  docs=418  consult=OK
✓ hardware_agent    status=healthy  docs=9853 consult=OK
✓ telemetry_agent   status=healthy  docs=945  consult=OK
```

If any agent shows `consult=FAIL`, do not proceed — wait for DSPy initialisation to complete.

---

## 7. Thesis Reproducibility Note

All evaluation results in the thesis correspond to specific commits on the `dev` branch of this repository. The mapping is:

| Run | Commit | Branch |
|-----|--------|--------|
| Run 1 | pre-`db7aeff` | `dev` |
| Run 2 | `5bcbe39` | `dev` |
| Run 3 (invalid) | `1d41663` | `dev` |
| Run 4 | `1d41663` | `dev` (results retained in `results/ablation/`) |
| Run 5 (planned) | `ad30962` | `dev` |

Results are saved to `results/ablation/thesis_summary.json` after each complete run. Per-test-case breakdowns are in `results/ablation/{case_name}_ablation.json`.

---

## 8. Limitations and Threats to Validity

### 8.1 DSPy Field Parsing Reliability

Five test cases consistently produced empty DSPy output for hardware and telemetry agents in Run 4. The root cause is that DSPy's `ChainOfThought` relies on the LLM to produce output in a specific structured format. When query content is outside the training distribution of the DSPy signature's expected domain (e.g., a governance-oriented test case sent to the hardware agent), the LLM may generate a response that cannot be parsed into the expected output fields, resulting in `None` values throughout the Prediction object.

The Bug 1–4 fixes provide defensive handling for this condition (fallback chains, `_real()` filtering, extended `_is_empty_response()`), but they do not eliminate the underlying cause. If DSPy genuinely cannot parse a response for a test case, that test case will still score 0% for the affected modes.

### 8.2 Query Type Classification

All orchestrator-to-agent calls pass `is_symptom=True` by default (the `ConsultPayload.is_symptom` field default). This routes all queries through governance's `ProfileInstitution` DSPy signature, which is optimised for institutional context queries. Queries that are primarily hardware fault queries (e.g., `rf_amplifier_intermittent`) may not match the `ProfileInstitution` input schema well, producing None for `contextual_explanation` while succeeding on `institution_profile`. The context injection parity fix partly mitigates this by including hardware context directly in the query, but the fundamental routing remains unchanged.

### 8.3 Keyword Accuracy as Primary Metric

Keyword accuracy is a brittle metric: a correct diagnosis expressed in different terminology scores 0 for missing keywords. The LLM-as-Judge and semantic similarity instruments were added specifically to mitigate this. The emergence criterion uses a dual-condition check (keyword accuracy margin AND cross-domain reference OR judge cross-domain score) to reduce false negatives from keyword sensitivity.

### 8.4 Single Evaluation Run per Configuration

Due to API cost constraints, each configuration (combination of fixes) is evaluated once rather than multiple times with averaged results. This means individual run noise cannot be separated from systematic effects. The per-test-case results should be interpreted as point estimates rather than stable means.

---

*End of evaluation process log.*
