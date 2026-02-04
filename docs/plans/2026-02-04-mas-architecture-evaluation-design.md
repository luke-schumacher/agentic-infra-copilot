# Multi-Agent System Architecture & Evaluation Design

**Date**: 2026-02-04
**Status**: Draft
**Author**: Brainstorming session output

---

## Executive Summary

This document defines the architecture and evaluation framework for a domain-agnostic Multi-Agent System (MAS) for fault diagnosis. The design addresses two critical gaps:

1. **Autonomy**: Agents can refuse, clarify, redirect, and consult peers
2. **Emergence**: The system produces insights no single agent could reach alone

The framework uses three role-based agents (Governance, Hardware, Telemetry) with a multi-round dialogue protocol, validated through ablation testing and multiple evaluation sources.

---

## 1. Design Philosophy

### Core Principle

Agents behave like real specialists in consultation. When a doctor consults a radiologist, the radiologist might:
- "Yes, I see a shadow on the scan" (confident answer)
- "I need the patient history to interpret this" (clarification)
- "This looks more like a cardiology issue" (redirect)
- "The image quality is too low to diagnose" (refuse with reason)

Agents should do the same. This creates realistic autonomy that naturally leads to emergence.

### The Emergence Mechanism

Emergence happens when agents disagree or build on each other:

```
Governance: "SLA breach detected"
    → Delegates to Hardware
Hardware: "Hardware nominal, but I see unusual power cycles"
    → Suggests also consulting Telemetry
Telemetry: "Power cycles correlate with session spikes"
    → Returns to Governance
Governance: "Root cause: load pattern, not hardware or SLA config"
```

No single agent could reach this. The back-and-forth negotiation surfaces the insight.

### Key Architectural Changes

1. Agents evaluate requests before answering
2. Agents can request peer consultation
3. Governance facilitates multi-round dialogue
4. Final synthesis shows reasoning chain across agents

---

## 2. Agent Naming

Role-based naming for domain-agnostic architecture:

| Old Name | New Name | Role |
|----------|----------|------|
| Telekom Minister | **Governance Agent** | SLAs, compliance, policy |
| Siemens Technician | **Hardware Agent** | Equipment, physical faults |
| Illigo Operator | **Telemetry Agent** | Events, logs, live monitoring |

---

## 3. Autonomy Protocol

### Response Types

Each agent, before answering, runs an evaluation step. The response can be:

| Response Type | When Used | Contains |
|---------------|-----------|----------|
| `ANSWER` | Agent can handle confidently | Diagnosis + confidence score |
| `PARTIAL` | Agent has relevant info but incomplete | Partial findings + what's missing |
| `CLARIFY` | Need more context to proceed | Specific questions to ask |
| `REDIRECT` | Wrong agent for this query | Suggested agent + reason |
| `REFUSE` | Cannot help at all | Reason (no data, out of scope) |
| `CONSULT` | Can answer but wants peer input | Partial answer + who to consult |

### AgentResponse Schema

```python
class AgentResponse(BaseModel):
    response_type: ResponseType  # ANSWER, PARTIAL, CLARIFY, REDIRECT, REFUSE, CONSULT
    confidence: float  # 0.0 - 1.0
    findings: Optional[str]  # What I found (if any)
    reasoning: str  # Why I'm responding this way

    # For CLARIFY
    clarification_questions: Optional[List[str]]

    # For REDIRECT or CONSULT
    suggested_agent: Optional[str]
    consultation_reason: Optional[str]

    # For PARTIAL
    missing_information: Optional[str]
```

### Evaluation Signature (Each Agent)

```python
class EvaluateRequest(dspy.Signature):
    """Evaluate if I can handle this request before attempting diagnosis"""
    query: str = dspy.InputField()
    my_expertise: str = dspy.InputField()  # "MRI hardware, Siemens equipment"
    available_data: str = dspy.InputField()  # Retrieved context summary

    can_fully_answer: bool = dspy.OutputField()
    confidence_level: float = dspy.OutputField()
    response_type: str = dspy.OutputField()  # ANSWER/PARTIAL/CLARIFY/REDIRECT/REFUSE/CONSULT
    reasoning: str = dspy.OutputField()
    suggested_agent: str = dspy.OutputField()  # If REDIRECT/CONSULT
    missing_info: str = dspy.OutputField()  # If PARTIAL/CLARIFY
```

---

## 4. Multi-Round Dialogue Protocol

### Current vs Proposed Flow

**Current (single round):**
```
User → Governance → Specialist → Governance → User
```

**Proposed (multi-round):**
```
User → Governance → Specialist A → (CONSULT) → Specialist B → Governance integrates → User
                  ↓
            (CLARIFY) → Governance asks user → continues
                  ↓
            (PARTIAL) → Governance seeks more agents → continues
```

### Protocol Rules

1. **Max rounds**: Cap at 3-4 to prevent infinite loops
2. **Governance orchestrates**: Always returns to Governance between specialist calls
3. **Accumulating context**: Each round adds to shared understanding
4. **Termination conditions**: All agents answered, or confidence threshold reached

### DiagnosisSession Schema

```python
class DiagnosisSession(BaseModel):
    session_id: str
    original_query: str
    current_round: int
    max_rounds: int = 4

    # Accumulated findings
    agent_responses: List[AgentResponse]
    reasoning_chain: List[str]

    # State tracking
    agents_consulted: Set[str]
    pending_clarifications: List[str]
    current_confidence: float

    # Termination
    is_complete: bool
    termination_reason: str  # "confidence_reached", "max_rounds", "all_consulted"
```

### Round Orchestration Logic

```python
def orchestrate_round(session: DiagnosisSession, latest_response: AgentResponse):
    if latest_response.response_type == "ANSWER" and latest_response.confidence > 0.8:
        return finalize_diagnosis(session)

    elif latest_response.response_type == "CONSULT":
        # Agent wants peer input - honor the request
        next_agent = latest_response.suggested_agent
        return delegate_to(next_agent, include_context=session.reasoning_chain)

    elif latest_response.response_type == "PARTIAL":
        # Agent has partial info - try another agent
        unconsulted = get_unconsulted_agents(session)
        if unconsulted:
            return delegate_to(unconsulted[0], include_context=latest_response.findings)
        else:
            return synthesize_partial_findings(session)

    elif latest_response.response_type == "CLARIFY":
        # Need user input - pause and ask
        return request_user_clarification(latest_response.clarification_questions)

    elif session.current_round >= session.max_rounds:
        return synthesize_best_effort(session)
```

---

## 5. Emergence Test Cases

### Test Case Structure

```python
class EmergenceTestCase(BaseModel):
    name: str
    description: str

    # What each agent sees in isolation
    governance_context: str   # SLA data, policy docs
    hardware_context: str     # Equipment records, specs
    telemetry_context: str    # Event logs, metrics

    # What each agent concludes alone (should be incomplete/wrong)
    governance_alone: str     # "SLA breach, penalize vendor"
    hardware_alone: str       # "Sensor needs replacement"
    telemetry_alone: str      # "Software timeout detected"

    # The correct integrated answer (only MAS gets this)
    emergent_diagnosis: str   # The real root cause
    reasoning_chain: List[str]  # How agents build on each other

    # Evaluation criteria
    requires_cross_domain: bool  # True = only MAS can solve
    difficulty: str  # simple, moderate, complex
```

### Example Test Case: Cascading Thermal Fault

| Field | Value |
|-------|-------|
| **Name** | Cascading Thermal Fault |
| **Governance sees** | "Uptime SLA breached: 94% vs 99% target" |
| **Hardware sees** | "Temperature sensor shows intermittent readings" |
| **Telemetry sees** | "Session failures every 90 minutes" |
| **Governance alone** | "Vendor breach, initiate penalty clause" |
| **Hardware alone** | "Replace temperature sensor" |
| **Telemetry alone** | "Increase session timeout threshold" |
| **Emergent diagnosis** | "Intermittent sensor triggers thermal safety shutdown every 90 min, causing session drops and SLA breach. Root cause: sensor calibration, not vendor or software." |
| **Reasoning chain** | 1. Telemetry: "90-min pattern exists" → 2. Hardware: "Thermal cycle matches pattern" → 3. Governance: "Root cause is hardware, not vendor SLA" |

---

## 6. Evaluation Framework

### Three Evaluation Layers

| Layer | What It Measures | Method |
|-------|------------------|--------|
| **Automated Metrics** | Accuracy, performance, consistency | Programmatic scoring against ground truth |
| **LLM-as-Judge** | Reasoning quality, coherence, actionability | Secondary LLM evaluates outputs |
| **Ablation Analysis** | Emergence proof, agent contribution | Compare MAS vs single-agent vs isolated agents |

### Automated Metrics Suite

```python
class AutomatedMetrics(BaseModel):
    # Accuracy (priority #1)
    root_cause_match: bool          # Exact match to ground truth
    root_cause_similarity: float    # Semantic similarity if not exact
    false_positive_rate: float      # Wrong diagnoses
    false_negative_rate: float      # Missed diagnoses

    # Actionability (priority #2)
    recommended_actions_valid: bool # Are actions appropriate?
    action_specificity: float       # Generic vs specific guidance

    # Reasoning (priority #3)
    reasoning_steps_count: int      # Length of chain
    evidence_citations: int         # References to source data
    cross_domain_links: int         # References across agent domains

    # Performance
    total_rounds: int               # Dialogue rounds needed
    total_latency_ms: float         # End-to-end time
    tokens_consumed: int            # Cost tracking
```

### LLM-as-Judge Evaluation

```python
class JudgeEvaluation(dspy.Signature):
    """Evaluate diagnosis quality"""
    query: str = dspy.InputField()
    ground_truth: str = dspy.InputField()
    system_diagnosis: str = dspy.InputField()
    reasoning_chain: str = dspy.InputField()

    accuracy_score: int = dspy.OutputField(desc="1-5: How correct is the diagnosis?")
    actionability_score: int = dspy.OutputField(desc="1-5: How actionable are recommendations?")
    reasoning_score: int = dspy.OutputField(desc="1-5: How coherent is the reasoning?")
    emergence_detected: bool = dspy.OutputField(desc="Does reasoning show cross-domain synthesis?")
    critique: str = dspy.OutputField(desc="Specific feedback on the diagnosis")
```

### Multiple Judge Sources

For robustness, use multiple evaluators:
- Judge 1: GPT-4 (different model family)
- Judge 2: Claude (another perspective)
- Judge 3: Human expert (gold standard, subset of cases)

Take median/consensus across judges to reduce bias.

### Ablation Testing

Run each test case in five modes:

| Mode | Description | Expected Outcome |
|------|-------------|------------------|
| Governance Only | Single agent with only governance data | Wrong/incomplete |
| Hardware Only | Single agent with only hardware data | Wrong/incomplete |
| Telemetry Only | Single agent with only telemetry data | Wrong/incomplete |
| Single + All Data | One agent with all three data sources | May pattern-match correctly |
| **MAS (Full)** | All agents collaborating | Correct with reasoning chain |

### Emergence Indicator

> If MAS accuracy > max(ablation accuracies) AND MAS produces reasoning chains that reference multiple domains → **emergence demonstrated**

---

## 7. Visualizations

### 7.1 Ablation Comparison Chart

```
Accuracy by Mode (Bar Chart)
─────────────────────────────────
Governance Only    ████░░░░░░  38%
Hardware Only      █████░░░░░  45%
Telemetry Only     ███░░░░░░░  32%
Single + All Data  ███████░░░  71%
MAS (Full System)  █████████░  92%
                   ─────────────────
                   0%        100%
```

### 7.2 Reasoning Chain Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Governance  │     │  Hardware   │     │  Telemetry  │
│             │     │             │     │             │
│ "SLA breach │────▶│ "Sensor has │────▶│ "90-min     │
│  detected"  │     │  drift"     │     │  pattern"   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                    ┌──────▼──────┐
                    │  EMERGENT   │
                    │ "Sensor     │
                    │ calibration │
                    │ root cause" │
                    └─────────────┘
```

### 7.3 Confidence Progression

```
Confidence Over Dialogue Rounds
─────────────────────────────────
1.0│                    ●━━━━━━━
   │               ●────┘
0.5│          ●────┘
   │     ●────┘
0.0│─●───┴──────────────────────
   └─────────────────────────────
     R1   R2   R3   R4   Final
```

### 7.4 Emergence Heatmap

```
Cross-Domain References Matrix
───────────────────────────────
           Gov   Hdw   Tel
         ┌─────┬─────┬─────┐
Gov      │  -  │ 23  │ 18  │
         ├─────┼─────┼─────┤
Hdw      │ 15  │  -  │ 31  │
         ├─────┼─────┼─────┤
Tel      │ 12  │ 27  │  -  │
         └─────┴─────┴─────┘
```

### Logging for Visualizations

```python
class DiagnosisLog(BaseModel):
    """Log everything needed for visualization"""
    session_id: str
    test_case_id: str

    # Per-round tracking
    rounds: List[RoundLog]

    # Final outcomes
    final_diagnosis: str
    ground_truth: str
    accuracy_score: float

    # Emergence evidence
    cross_domain_refs: List[CrossDomainReference]
    reasoning_chain: List[ReasoningStep]

class RoundLog(BaseModel):
    round_number: int
    agent: str
    response_type: str
    confidence: float
    findings_summary: str
    cited_agents: List[str]  # For emergence tracking
```

---

## 8. Implementation Roadmap

### Phase 1: Protocol Foundation

| Task | Description |
|------|-------------|
| Rename agents | Governance, Hardware, Telemetry |
| Add `ResponseType` enum | ANSWER, PARTIAL, CLARIFY, REDIRECT, REFUSE, CONSULT |
| Add `EvaluateRequest` signature | Each agent evaluates before answering |
| Update `AgentCard` schema | Add confidence, response_type, suggested_agent fields |

### Phase 2: Multi-Round Dialogue

| Task | Description |
|------|-------------|
| Create `DiagnosisSession` | Tracks state across rounds |
| Update Governance orchestration | Handle all response types, accumulate context |
| Add round limits | Prevent infinite loops (max 4 rounds) |
| Implement `CONSULT` flow | Agent A requests Agent B mid-diagnosis |

### Phase 3: Evaluation Infrastructure

| Task | Description |
|------|-------------|
| Create `EmergenceTestCase` schema | Ground truth + expected outcomes |
| Build ablation test runner | Run same case in 5 modes |
| Implement `AutomatedMetrics` | Programmatic scoring |
| Implement `LLM-as-Judge` | Secondary evaluation |
| Add logging for visualizations | `DiagnosisLog`, `RoundLog` |

### Phase 4: Test Cases & Validation

| Task | Description |
|------|-------------|
| Design 10-15 emergence test cases | Covering simple → complex |
| Run baseline comparison | Single-agent vs MAS |
| Generate visualizations | Charts for thesis |
| Document findings | Results chapter |

### Dependencies

```
Phase 1 ──▶ Phase 2 ──▶ Phase 3 ──▶ Phase 4
                            │
                            ▼
                    (New Siemens data arrives)
                    Build domain-specific cases
```

---

## 9. Thesis Framing

### Two Deliverables

1. **Architecture Contribution**: A domain-agnostic multi-agent fault diagnosis framework with clear interfaces, autonomy protocol, and emergence-enabling dialogue

2. **Validation Case Study**: Application to Siemens Healthineers MRI data demonstrating the framework works

### Future Work

- Telekom integration for connected medical device scenarios
- Cross-domain data correlation (hardware faults → network issues → SLA breaches)
- Graph-based orchestration upgrade (LangGraph)

---

## 10. Open Questions

- [ ] What specific Siemens data fields enable cross-domain scenarios?
- [ ] Which LLM judges are accessible for evaluation?
- [ ] How many test cases are sufficient for thesis defense?
- [ ] Should Neo4j knowledge graph be integrated in Phase 1 or later?

---

## Appendix: Current Architecture Reference

See codebase exploration for current state:
- Agents: `src/agents/{governance,hardware,telemetry}/`
- Protocol: `src/protocol/schema.py`
- Orchestrator: `src/ui/app.py`
- Baseline mode: `BASELINE_MODE` environment variable
