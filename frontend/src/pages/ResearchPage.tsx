import { useState } from 'react';
import { FlaskConical, BookOpen, Target, CheckCircle, Circle, Layers, Users, BarChart2 } from 'lucide-react';
import styles from './ResearchPage.module.css';

// ─── Test cases ────────────────────────────────────────────────────────────

const TEST_CASES = [
  {
    name: 'cascading_thermal_fault',
    difficulty: 'moderate',
    domains: ['hardware', 'telemetry', 'governance'],
    description: 'Thermal sensor calibration drift causes 90-minute session failure cycle, triggering SLA breach.',
    singleDiagnosis: 'Each agent diagnoses its own slice: SLA breach, sensor drift, or session timeout.',
    emergentDiagnosis: 'Root cause is sensor calibration, not vendor SLA failure. Penalty should be waived.',
    keywords: ['calibration', 'sensor', '90-minute', 'thermal', 'waive'],
  },
  {
    name: 'phantom_load_spike',
    difficulty: 'complex',
    domains: ['hardware', 'telemetry'],
    description: 'Unexplained power load spikes correlate with specific scan protocols — hardware anomaly or telemetry artefact?',
    singleDiagnosis: 'Hardware sees load spike. Telemetry sees anomaly flags. Neither can correlate.',
    emergentDiagnosis: 'Specific gradient protocol triggers power amplifier saturation; correlate scan schedule with load events.',
    keywords: ['gradient', 'amplifier', 'protocol', 'saturation', 'schedule'],
  },
  {
    name: 'gradient_coil_degradation',
    difficulty: 'complex',
    domains: ['hardware', 'telemetry'],
    description: 'Gradual gradient coil performance decline manifests as subtle image artefacts before hard failure.',
    singleDiagnosis: 'Hardware: coil spec deviation. Telemetry: increasing error rate trend.',
    emergentDiagnosis: 'Degradation trajectory predicts failure window; proactive replacement before SLA breach.',
    keywords: ['coil', 'degradation', 'trajectory', 'preventive', 'artefact'],
  },
  {
    name: 'helium_boiloff_cascade',
    difficulty: 'complex',
    domains: ['hardware', 'telemetry', 'governance'],
    description: 'Helium boil-off rate increase cascades to quench risk, maintenance schedule conflict, and downtime SLA.',
    singleDiagnosis: 'Hardware: boiloff rate. Governance: maintenance schedule. No cross-domain synthesis.',
    emergentDiagnosis: 'Accelerated boiloff + upcoming maintenance gap = high quench probability. Emergency refill required.',
    keywords: ['helium', 'boiloff', 'quench', 'maintenance', 'emergency'],
  },
  {
    name: 'software_update_regression',
    difficulty: 'moderate',
    domains: ['hardware', 'governance'],
    description: 'Post-update DICOM conformance failure linked to change management gap.',
    singleDiagnosis: 'Hardware: DICOM non-conformance. Governance: no change record.',
    emergentDiagnosis: 'Update rolled back without test validation; change management SOP violated.',
    keywords: ['DICOM', 'rollback', 'change', 'SOP', 'validation'],
  },
  {
    name: 'rf_amplifier_intermittent',
    difficulty: 'moderate',
    domains: ['hardware', 'telemetry'],
    description: 'Intermittent RF amplifier faults correlate with temperature — difficult to reproduce.',
    singleDiagnosis: 'Hardware: intermittent fault code. Telemetry: sporadic error events.',
    emergentDiagnosis: 'Temperature-dependent failure; fault only manifests above 24°C ambient. AC unit under-specced.',
    keywords: ['RF', 'amplifier', 'temperature', 'ambient', 'intermittent'],
  },
  {
    name: 'missed_maintenance_escalation',
    difficulty: 'simple',
    domains: ['governance', 'hardware'],
    description: 'Preventive maintenance overdue; escalation policy not triggered.',
    singleDiagnosis: 'Governance: PM overdue. Hardware: component wear indicators present.',
    emergentDiagnosis: 'Wear indicators + overdue PM = high failure probability; escalate to vendor within 48 hours.',
    keywords: ['maintenance', 'overdue', 'wear', 'escalate', 'preventive'],
  },
  {
    name: 'network_false_alarm',
    difficulty: 'moderate',
    domains: ['telemetry', 'hardware'],
    description: 'Network event falsely flagged as scanner hardware fault due to DICOM timeout.',
    singleDiagnosis: 'Telemetry: DICOM timeout. Hardware: no fault found.',
    emergentDiagnosis: 'Root cause is hospital network congestion, not scanner hardware. No service call needed.',
    keywords: ['network', 'DICOM', 'timeout', 'congestion', 'false alarm'],
  },
  {
    name: 'protocol_conflict_sla',
    difficulty: 'moderate',
    domains: ['governance', 'telemetry'],
    description: 'New scan protocol violates safety SOP, causing compliance flag and SLA measurement confusion.',
    singleDiagnosis: 'Governance: SLA metric ambiguous. Telemetry: safety flag triggered.',
    emergentDiagnosis: 'Protocol change requires SOP amendment and SLA renegotiation; safety flag is legitimate.',
    keywords: ['protocol', 'SOP', 'SLA', 'compliance', 'renegotiate'],
  },
  {
    name: 'known_fault_code_lookup',
    difficulty: 'simple',
    domains: ['hardware'],
    description: 'Standard error code lookup with known resolution procedure.',
    singleDiagnosis: 'Hardware: FM-007 gradient cooling fault — standard procedure.',
    emergentDiagnosis: 'Direct lookup — single-agent sufficient. MAS adds no emergence value.',
    keywords: ['FM-007', 'gradient', 'cooling', 'resolution', 'procedure'],
  },
  {
    name: 'shimming_environmental',
    difficulty: 'complex',
    domains: ['hardware', 'telemetry', 'governance'],
    description: 'Shimming degradation driven by environmental changes — seasonal temperature variation near scanner room.',
    singleDiagnosis: 'Hardware: shimming drift. Telemetry: seasonal pattern. Governance: no room spec on file.',
    emergentDiagnosis: 'Temperature control in scanner room inadequate; seasonal recalibration schedule required.',
    keywords: ['shimming', 'temperature', 'seasonal', 'calibration', 'environment'],
  },
  {
    name: 'multi_scanner_cooling',
    difficulty: 'complex',
    domains: ['hardware', 'telemetry', 'governance'],
    description: 'Shared cooling infrastructure fails when two scanners run simultaneous high-SAR protocols.',
    singleDiagnosis: 'Hardware: cooling overload on scanner 1. No cross-scanner context.',
    emergentDiagnosis: 'Shared cooling capacity insufficient for concurrent peak workloads; schedule staggering required.',
    keywords: ['cooling', 'SAR', 'concurrent', 'stagger', 'infrastructure'],
  },
];

const CONTRIBUTIONS = [
  {
    title: 'Tripartite MAS for MRI diagnostics',
    desc: 'Production-ready system with Governance (Anthropologist), Hardware (Specialist), and Telemetry (Auditor) agents on isolated FastAPI services.',
  },
  {
    title: 'Federated Agentic RAG with cognitive silos',
    desc: 'Novel SILO_ALLOWED_TYPES enforcement in ChromaDB — domain boundaries are architecturally enforced, not just by prompt instruction.',
  },
  {
    title: 'A2A AgentCard protocol',
    desc: 'Custom JSON-LD-inspired schema with 6 typed response states (ANSWER/PARTIAL/CLARIFY/REDIRECT/REFUSE/CONSULT) driving the autonomy protocol.',
  },
  {
    title: 'Three-tier LLM strategy via DSPy',
    desc: 'GPT-4.1 router (temp=0.0) → Haiku reasoner (global default) → Sonnet judge/synthesiser. Model selection is backed by ablation evidence.',
  },
  {
    title: 'Empirical emergence measurement',
    desc: 'Dual-criterion emergence detection: accuracy margin + cross-domain reference count or judge cross-domain score > 0.5.',
  },
  {
    title: 'Siemens Healthineers real-world data integration',
    desc: 'De-identified DICOM event logs, MAGNETOM operator manuals, DCS documentation, safety SOPs, and MRRT questionnaires.',
  },
  {
    title: 'React evaluation frontend with live run control',
    desc: 'EvaluationPanel with per-case test case selection, resume support, real-time progress polling, and agent data readiness checks.',
  },
];

const LIMITATIONS = [
  { item: 'Ground truth authored by single researcher', mitigation: 'Mitigated by keyword-level specificity and structured scoring rubric' },
  { item: 'LLM-as-judge introduces model-specific scoring bias', mitigation: 'Consistent judge (Sonnet 4.5) across all modes ensures fair comparison' },
  { item: 'Test set limited to 12 scenarios', mitigation: 'Run 3 extends to longer evaluation; 12 cases cover all difficulty tiers' },
  { item: 'Synchronous A2A delegation adds latency', mitigation: 'Specialists called in parallel via asyncio.gather() — latency = max, not sum' },
  { item: 'Azure rate limits constrain parallelism at scale', mitigation: 'Rate-limit delays added in runner; resume support prevents re-running completed cases' },
  { item: 'Patient data fully de-identified — no real clinical deployment', mitigation: 'Scope is infrastructure diagnostics; clinical data not required for research question' },
];

const RELATED_WORK = [
  { category: 'Multi-Agent Systems', refs: ['AutoGen (Microsoft, 2023)', 'CrewAI', 'LangGraph', 'CAMEL'] },
  { category: 'Agentic RAG', refs: ['Federated RAG (Lewis et al.)', 'Self-RAG', 'RAPTOR recursive retrieval'] },
  { category: 'LLM-as-Judge', refs: ['MT-Bench (Zheng et al., 2023)', 'Judging LLM-as-a-Judge (Zheng et al.)'] },
  { category: 'MRI Informatics', refs: ['ACR Appropriateness Criteria', 'DICOM PS3.x', 'MRRT IHE standard'] },
  { category: 'DSPy Framework', refs: ['DSPy: Compiling Declarative LM Programs (Khattab et al., 2023)'] },
];

export function ResearchPage() {
  const [activeTab, setActiveTab] = useState<'overview' | 'cases' | 'contributions' | 'limitations' | 'related'>('overview');
  const [expandedCase, setExpandedCase] = useState<string | null>(null);

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerTitle}>
          <FlaskConical size={20} />
          Research Context
        </div>
        <div className={styles.headerMeta}>
          MSc thesis — Agentic Infrastructure Co-Pilot for MRI Diagnostics · Siemens Healthineers data
        </div>
      </div>

      <div className={styles.tabs}>
        {([
          ['overview',      'Overview',       BookOpen],
          ['cases',         'Test Cases',     BarChart2],
          ['contributions', 'Contributions',  CheckCircle],
          ['limitations',   'Limitations',    Circle],
          ['related',       'Related Work',   Layers],
        ] as const).map(([id, label, Icon]) => (
          <button
            key={id}
            className={`${styles.tab} ${activeTab === id ? styles.tabActive : ''}`}
            onClick={() => setActiveTab(id)}
          >
            <Icon size={13} />
            {label}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW ───────────────────────────────────── */}
      {activeTab === 'overview' && (
        <div className={styles.tabContent}>
          <section className={styles.section}>
            <div className={styles.sectionTitle}><BookOpen size={14} /> Problem Statement</div>
            <div className={styles.prose}>
              <p>
                MRI infrastructure management in radiology departments involves complex, multi-domain
                decision-making spanning hardware diagnostics, safety compliance, and institutional
                governance. Current approaches rely on isolated specialist knowledge: engineers handle
                equipment faults, safety officers check SOP compliance, and administrators manage SLAs —
                with no systematic mechanism for cross-domain synthesis.
              </p>
              <p>
                This thesis investigates whether a tripartite Multi-Agent System (MAS), with
                domain-specialised agents and federated knowledge bases, can demonstrably outperform
                single-agent baselines through emergent cross-domain reasoning. The key question: does
                coordination itself add diagnostic value beyond what a single agent with complete data
                can achieve?
              </p>
            </div>
          </section>

          <section className={styles.section}>
            <div className={styles.sectionTitle}><Target size={14} /> Hypotheses</div>
            <div className={styles.hypothesisList}>
              {[
                {
                  id: 'H1',
                  text: 'A tripartite MAS with domain-specialised agents and federated RAG will achieve higher diagnostic accuracy on complex, cross-domain MRI infrastructure queries than any single-agent baseline — including a single agent given access to all data (Single+All).',
                },
                {
                  id: 'H2',
                  text: 'The performance advantage of MAS will be most pronounced for queries requiring synthesis across two or more domains (complex difficulty), where no single specialist can provide a complete diagnosis.',
                },
                {
                  id: 'H3',
                  text: 'The cross-domain synthesis step (Claude Sonnet 4.5 as synthesiser) accounts for a measurable portion of the MAS performance advantage over individual Haiku-driven specialist responses.',
                },
              ].map((h) => (
                <div key={h.id} className={styles.hypothesisItem}>
                  <span className={styles.hBadge}>{h.id}</span>
                  <p>{h.text}</p>
                </div>
              ))}
            </div>
          </section>

          <section className={styles.section}>
            <div className={styles.sectionTitle}><Target size={14} /> Research Questions</div>
            <div className={styles.rqList}>
              {[
                'Does MAS emergence — where MAS accuracy exceeds best single-agent — occur for complex cross-domain queries, and is it measurable via the dual-criterion emergence detector?',
                'Does federated RAG (domain-restricted silos) improve diagnostic accuracy over a unified single-agent RAG store with the same data?',
                'What is the role of the cross-domain synthesis step (Sonnet) in the overall performance gain?',
                'How does query difficulty (simple/moderate/complex) moderate MAS advantage — does emergence grow with complexity?',
                'Can the LLM-as-judge (Sonnet 4.5) produce reliable, consistent scores that correlate with keyword-based accuracy metrics?',
              ].map((rq, i) => (
                <div key={i} className={styles.rqItem}>
                  <div className={styles.rqIndex}>RQ{i + 1}</div>
                  <div className={styles.rqText}>{rq}</div>
                </div>
              ))}
            </div>
          </section>

          <section className={styles.section}>
            <div className={styles.sectionTitle}><Layers size={14} /> Methodology</div>
            <div className={styles.methodGrid}>
              {[
                {
                  label: 'Design',
                  detail: 'Controlled ablation study. 5 evaluation modes × 12 test cases = 60 evaluations per run. Each mode isolates one independent variable.',
                },
                {
                  label: 'Test Cases',
                  detail: '12 standardised scenarios across 3 difficulty tiers (2 simple, 5 moderate, 5 complex). Each has manually authored ground truth and required keywords.',
                },
                {
                  label: 'Evaluation',
                  detail: 'LLM-as-judge (Claude Sonnet 4.5) scoring 4 metrics: accuracy (0.35), relevance (0.20), completeness (0.20), cross-domain (0.25). Pass threshold: 0.60.',
                },
                {
                  label: 'Emergence Detection',
                  detail: 'Dual criterion: (1) MAS accuracy > best single-agent AND (2) cross_domain_refs > 0 OR judge cross_domain score > 0.5.',
                },
                {
                  label: 'Data',
                  detail: 'Siemens Healthineers: de-identified DICOM event logs, MAGNETOM operator manuals, DCS documentation, MRI SOPs, ACR criteria, MRRT questionnaires.',
                },
                {
                  label: 'Validity',
                  detail: 'Consistent judge model across all modes. Keyword-based fallback for cross-validation. Resume support prevents partial-run contamination.',
                },
              ].map((m) => (
                <div key={m.label} className={styles.methodCard}>
                  <div className={styles.methodLabel}>{m.label}</div>
                  <p className={styles.methodDetail}>{m.detail}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}

      {/* ── TEST CASES ─────────────────────────────────── */}
      {activeTab === 'cases' && (
        <div className={styles.tabContent}>
          <div className={styles.casesIntro}>
            <Users size={14} />
            <span>
              12 standardised test cases designed to require cross-domain synthesis.
              Each has manually authored ground truth, required keywords, and expected agent sequence.
              Single-agent baselines are specifically designed to <em>fail</em> on cross-domain cases.
            </span>
          </div>

          <div className={styles.casesGrid}>
            {TEST_CASES.map((tc) => (
              <div
                key={tc.name}
                className={`${styles.caseCard} ${expandedCase === tc.name ? styles.caseExpanded : ''}`}
                onClick={() => setExpandedCase(expandedCase === tc.name ? null : tc.name)}
              >
                <div className={styles.caseHeader}>
                  <div className={styles.caseName}>{tc.name.replace(/_/g, ' ')}</div>
                  <span className={styles.diffBadge} data-difficulty={tc.difficulty}>{tc.difficulty}</span>
                </div>
                <div className={styles.caseDomains}>
                  {tc.domains.map((d) => (
                    <span key={d} className={`${styles.domainTag} ${styles[`domain_${d}`]}`}>{d}</span>
                  ))}
                </div>
                <p className={styles.caseDesc}>{tc.description}</p>

                {expandedCase === tc.name && (
                  <div className={styles.caseExpansion}>
                    <div className={styles.caseRow}>
                      <span className={styles.caseRowLabel}>Single-agent failure mode</span>
                      <span className={styles.caseRowValue}>{tc.singleDiagnosis}</span>
                    </div>
                    <div className={styles.caseRow}>
                      <span className={styles.caseRowLabel}>Emergent diagnosis</span>
                      <span className={`${styles.caseRowValue} ${styles.caseEmergent}`}>{tc.emergentDiagnosis}</span>
                    </div>
                    <div className={styles.caseKeywords}>
                      <span className={styles.caseRowLabel}>Required keywords</span>
                      <div className={styles.keywordTags}>
                        {tc.keywords.map((k) => (
                          <span key={k} className={styles.keywordTag}>{k}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                <div className={styles.caseHint}>{expandedCase === tc.name ? '▲ collapse' : '▼ expand'}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── CONTRIBUTIONS ──────────────────────────────── */}
      {activeTab === 'contributions' && (
        <div className={styles.tabContent}>
          <div className={styles.contribList}>
            {CONTRIBUTIONS.map((c, i) => (
              <div key={i} className={styles.contribCard}>
                <div className={styles.contribHeader}>
                  <CheckCircle size={15} className={styles.contribIcon} />
                  <span className={styles.contribTitle}>{c.title}</span>
                </div>
                <p className={styles.contribDesc}>{c.desc}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── LIMITATIONS ────────────────────────────────── */}
      {activeTab === 'limitations' && (
        <div className={styles.tabContent}>
          <div className={styles.limitsIntro}>
            Known limitations of the current design and how they are mitigated within the thesis scope.
          </div>
          <div className={styles.limitTable}>
            {LIMITATIONS.map((l, i) => (
              <div key={i} className={styles.limitRow}>
                <div className={styles.limitItem}>{l.item}</div>
                <div className={styles.limitMitigation}>{l.mitigation}</div>
              </div>
            ))}
          </div>
          <div className={styles.futureNote}>
            <div className={styles.sectionTitle}><Target size={13} /> Future Work</div>
            <div className={styles.futureList}>
              {[
                'Multi-rater ground truth validation with domain expert panel',
                'Real-time telemetry ingestion via DICOM network listener',
                'Extension to CT, PET, and ultrasound modalities',
                'Federated RAG architecture generalisation to other multi-domain diagnostic systems',
                'Adaptive routing that learns which specialist combination is optimal per query type',
                'Formal verification of SILO_ALLOWED_TYPES boundary enforcement',
              ].map((f, i) => (
                <div key={i} className={styles.futureItem}>
                  <span className={styles.futureDot} />
                  <span>{f}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── RELATED WORK ───────────────────────────────── */}
      {activeTab === 'related' && (
        <div className={styles.tabContent}>
          <div className={styles.relatedGrid}>
            {RELATED_WORK.map((rw) => (
              <div key={rw.category} className={styles.relatedCard}>
                <div className={styles.relatedCategory}>{rw.category}</div>
                <div className={styles.relatedRefs}>
                  {rw.refs.map((ref) => (
                    <div key={ref} className={styles.relatedRef}>{ref}</div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className={styles.positionNote}>
            <div className={styles.sectionTitle}><BookOpen size={13} /> Positioning</div>
            <div className={styles.positionBox}>
              <p>
                This work differs from existing multi-agent LLM systems (AutoGen, CrewAI) in its
                domain-enforced federated RAG architecture. While AutoGen focuses on code execution
                and CrewAI on task decomposition, this system enforces information provenance at
                the vector store level — agents cannot see each other's data without explicit synthesis.
              </p>
              <p>
                The emergence measurement methodology extends MT-Bench-style evaluation by adding a
                cross-domain synthesis dimension specifically designed to detect inter-agent
                coordination value. The ablation design (5 modes including Single+All) is novel in
                explicitly controlling for data access as an independent variable.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
