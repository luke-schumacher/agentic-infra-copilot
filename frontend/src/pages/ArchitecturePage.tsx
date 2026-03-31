import { useState } from 'react';
import { Network, Database, Brain, ArrowRight, Layers, GitMerge, Cpu, Shield } from 'lucide-react';
import styles from './ArchitecturePage.module.css';

// ─── Response type definitions ─────────────────────────────────────────────

const RESPONSE_TYPES = [
  {
    type: 'ANSWER',
    color: '#4ADE80',
    description: 'Complete, confident response. Confidence ≥ 0.8 and full context available. Triggers immediate finalisation.',
    trigger: 'High-confidence single-domain query where one agent has sufficient RAG context.',
    outcome: 'Response returned directly without specialist delegation.',
  },
  {
    type: 'CONSULT',
    color: '#60A5FA',
    description: 'Partial answer with cross-domain validation needed. The key emergence trigger — specifies suggested_agent and consultation_reason.',
    trigger: 'Agent has diagnosis but needs peer input (e.g. hardware fault also implicates safety compliance).',
    outcome: 'Suggested agent + all remaining unconsulted agents called in parallel via asyncio.gather().',
  },
  {
    type: 'PARTIAL',
    color: '#F5A623',
    description: 'Agent has some findings but is missing critical context from other domains.',
    trigger: 'Query spans multiple domains; current agent can only partially answer.',
    outcome: 'All unconsulted agents called in parallel; findings synthesised.',
  },
  {
    type: 'REDIRECT',
    color: '#A78BFA',
    description: 'Query belongs entirely to a different agent\'s domain. Agent suggests which specialist should own it.',
    trigger: 'Technical query sent to Governance Agent, or safety audit sent to Hardware Agent.',
    outcome: 'Suggested agent + remaining unconsulted agents called; best response used for next round.',
  },
  {
    type: 'CLARIFY',
    color: '#FB923C',
    description: 'Agent cannot proceed without additional user input. Generates specific clarification questions.',
    trigger: 'Ambiguous query — missing patient ID, scanner model, or institution type.',
    outcome: 'Session terminates with pending_clarifications list. User must respond to continue.',
  },
  {
    type: 'REFUSE',
    color: '#F87171',
    description: 'Agent cannot or should not answer — no data, out-of-scope, or safety concern.',
    trigger: 'Missing data for the specific scanner, query outside training data, or safety override.',
    outcome: 'Remaining unconsulted agents tried. If all refuse, best-effort synthesis returned.',
  },
];

// ─── Agent definitions ─────────────────────────────────────────────────────

const AGENTS = [
  {
    id: 'governance',
    name: 'Governance Agent',
    persona: 'The Anthropologist',
    port: 8001,
    color: '#60A5FA',
    badge: 'GOV',
    description: 'Workflow orchestrator and context manager. Entry point for all queries. Routes intent, delegates to specialists, integrates findings, and synthesises cross-domain responses.',
    dataSource: 'data/processed/governance',
    ragTypes: ['SLA contracts', 'Institutional policies', 'Workflow logs', 'Maintenance records', 'MRRT questionnaires'],
    signatures: ['EvaluateRequest', 'ProfileInstitution', 'AnalyzeWorkloadPattern', 'DelegateToSpecialist', 'IntegrateFindings', 'AnswerGeneralQuery'],
  },
  {
    id: 'hardware',
    name: 'Hardware Agent',
    persona: 'The Specialist',
    port: 8002,
    color: '#F5A623',
    badge: 'HW',
    description: 'Technical diagnostic specialist for MRI hardware. Analyses DICOM conformance, failure modes, error profiles, operator manuals, and DCS documentation.',
    dataSource: 'data/processed/hardware',
    ragTypes: ['DICOM conformance', 'Failure modes', 'Error profiles', 'Operator manuals', 'DCS documentation', 'Event log errors'],
    signatures: ['EvaluateRequest', 'DiagnoseDICOMFailure', 'AnalyzeHardwareError', 'LookupTechnicalSpec', 'CrossReferenceSOP', 'AnalyzeEventLogs', 'AnswerGeneralQuery'],
  },
  {
    id: 'telemetry',
    name: 'Telemetry Agent',
    persona: 'The Auditor',
    port: 8003,
    color: '#4ADE80',
    badge: 'TEL',
    description: 'Safety and compliance auditor. Cross-references safety zone definitions (I–IV), personnel requirements, MRI SOPs, and ACR appropriateness criteria against event telemetry.',
    dataSource: 'data/processed/telemetry',
    ragTypes: ['Safety zones I–IV', 'Personnel requirements', 'MRI SOP', 'ACR criteria', 'Safety event flags'],
    signatures: ['EvaluateRequest', 'ValidateComplianceSOP', 'ReviewDiagnosticAction', 'CheckSafetyZone', 'AuditWorkflowChange', 'AnswerGeneralQuery'],
  },
];

// ─── Multi-round flow steps ────────────────────────────────────────────────

const FLOW_STEPS = [
  {
    label: 'User query arrives',
    agent: null,
    detail: 'React frontend sends query + optional context (customer_id, scanner_model, institution_type, query_type) to Governance Agent on Port 8001.',
    code: 'POST /consult  →  AgentCard { intent: QUERY, payload: { query, context } }',
  },
  {
    label: 'Intent classification',
    agent: 'GOV',
    color: '#60A5FA',
    detail: 'GPT-4.1 router (temp=0.0) runs EvaluateRequest DSPy signature. Returns: can_fully_answer, confidence_level, response_type, suggested_agent.',
    code: 'EvaluateRequest → { response_type: "consult"|"answer"|"partial"|... }',
  },
  {
    label: 'RAG retrieval',
    agent: 'GOV',
    color: '#60A5FA',
    detail: 'Governance ChromaDB silo queried for SLA contracts, workload patterns, institution profiles. Neo4j enriches with fault-event-SLA relationship paths.',
    code: 'vector_store.query(k=5) + graph_service.get_enriched_context()',
  },
  {
    label: 'Specialist delegation (parallel)',
    agent: null,
    detail: 'If response_type is CONSULT / PARTIAL / REDIRECT, specialists are called in parallel via asyncio.gather(). Hardware and Telemetry agents receive delegation AgentCards simultaneously.',
    code: 'await asyncio.gather(*[call_agent(a, card) for a in specialists])',
  },
  {
    label: 'Specialist reasoning',
    agent: 'HW + TEL',
    color: '#F5A623',
    detail: 'Each specialist: (1) queries its isolated ChromaDB silo, (2) enriches with Neo4j graph context, (3) runs domain-specific DSPy ChainOfThought with Claude Haiku 4.5, (4) returns AgentCard with confidence + response_type.',
    code: 'brain.diagnose() → AgentCard { confidence, response_type, documents[] }',
  },
  {
    label: 'Multi-round continuation',
    agent: null,
    detail: 'Orchestrator loops up to 4 rounds. Each round calls orchestrate_round(session, latest_response). Terminates on: confidence ≥ 0.8, all agents consulted, max rounds reached, or user clarification needed.',
    code: 'while session.current_round < 4: orchestrate_round()',
  },
  {
    label: 'Cross-domain synthesis',
    agent: 'GOV',
    color: '#60A5FA',
    detail: 'Claude Sonnet 4.5 runs DiagnosisSynthesizer with labelled findings from all consulted agents. Produces unified root-cause diagnosis with cross-domain connections. Falls back to concatenation if Sonnet unavailable.',
    code: 'with dspy.context(lm=sonnet): synthesizer(query, findings_dict)',
  },
  {
    label: 'Response returned',
    agent: null,
    detail: 'Final AgentCard delivered to frontend: response_type, contextual_explanation, risk_level, recommended_actions, confidence, reasoning_chain, documents with relevance scores.',
    code: 'AgentCard { response_type: ANSWER|CONSULT, confidence, documents[], risk_level }',
  },
];

// ─── Tech stack ────────────────────────────────────────────────────────────

const TECH_STACK = [
  { layer: 'LLM Framework', value: 'DSPy ChainOfThought — structured prompting with typed signatures' },
  { layer: 'Router', value: 'GPT-4.1 via Azure (temp 0.0) — intent classification & routing' },
  { layer: 'Reasoner', value: 'Claude Haiku 4.5 via Azure — all three agent brains (global default)' },
  { layer: 'Judge / Synthesiser', value: 'Claude Sonnet 4.5 via Azure — evaluation scoring + cross-domain synthesis' },
  { layer: 'Vector store', value: 'ChromaDB — three isolated federated silos (one per agent)' },
  { layer: 'Embeddings', value: 'text-embedding-3-small (OpenAI) — 1536-dim dense embeddings' },
  { layer: 'Knowledge graph', value: 'Neo4j 5.15 (APOC) — 13 node types, 13 relationship types' },
  { layer: 'PDF ingestion', value: 'LangChain PyPDFLoader + RecursiveCharacterTextSplitter (1000/200)' },
  { layer: 'Agent framework', value: 'FastAPI (Python 3.11) — async HTTP, one service per agent' },
  { layer: 'A2A protocol', value: 'Custom AgentCard schema (JSON-LD-inspired) — correlation IDs, priority, response_type' },
  { layer: 'Frontend', value: 'React 18 + Vite + TypeScript — monorepo with CSS Modules' },
  { layer: 'Deployment', value: 'Docker Compose — 5 services (neo4j, gov, hw, tel, frontend)' },
];

// ─── Neo4j schema ──────────────────────────────────────────────────────────

const NEO4J_NODES = [
  { name: 'Scanner', props: 'scanner_id, model, manufacturer, location, install_date', example: 'MAGNETOM Sola / Vida / Altea / Free.Max' },
  { name: 'Component', props: 'component_id, name, type, scanner_id, expected_life_years', example: 'Gradient coil, RF amplifier, cryogen system' },
  { name: 'Fault', props: 'fault_id, failure_mode, severity, component, mttr_hours', example: 'FM-001 thermal sensor drift' },
  { name: 'Event', props: 'event_id, timestamp, level, source, description', example: 'ERROR: gradient overtemp at 14:23' },
  { name: 'Protocol', props: 'protocol_id, title, modality, body_region', example: 'Cardiac MRI, brain 3T' },
  { name: 'SLA', props: 'sla_id, name, metric, threshold, domain', example: 'Uptime ≥ 99%, completion rate ≥ 95%' },
  { name: 'RadLexTerm', props: 'code, meaning', example: 'RID10301 — magnetic resonance imaging' },
];

const NEO4J_RELS = [
  { rel: 'CAUSES', desc: 'Fault/Event → Fault/Event: causal chain in failure cascade' },
  { rel: 'DETECTED_BY', desc: 'Fault → Event: telemetry detection of hardware fault' },
  { rel: 'PART_OF', desc: 'Component → Scanner: physical composition' },
  { rel: 'VIOLATES', desc: 'Fault/Event → SLA: SLA breach linkage' },
  { rel: 'TRIGGERS', desc: 'Event → Fault: event triggering downstream fault' },
  { rel: 'RESOLVES', desc: 'Procedure → Fault: repair action resolves fault' },
  { rel: 'FOLLOWS', desc: 'Event → Event: temporal sequence in event log' },
];

// ─── Component ─────────────────────────────────────────────────────────────

function DiffBadge({ label, color }: { label: string; color: string }) {
  return (
    <span className={styles.typeBadge} style={{ background: `${color}22`, color, borderColor: `${color}44` }}>
      {label}
    </span>
  );
}

export function ArchitecturePage() {
  const [activeTab, setActiveTab] = useState<'agents' | 'flow' | 'protocol' | 'graph' | 'stack'>('agents');

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerTitle}>
          <Network size={20} />
          System Architecture
        </div>
        <div className={styles.headerMeta}>
          Tripartite Multi-Agent System · Federated Agentic RAG · A2A AgentCard Protocol
        </div>
      </div>

      <div className={styles.tabs}>
        {([
          ['agents', 'Agent Roles', Brain],
          ['flow',   'Query Flow',  ArrowRight],
          ['protocol', 'Response Protocol', GitMerge],
          ['graph',  'Knowledge Graph', Database],
          ['stack',  'Tech Stack', Layers],
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

      {/* ── AGENTS TAB ─────────────────────────────────── */}
      {activeTab === 'agents' && (
        <div className={styles.tabContent}>
          <div className={styles.agentGrid}>
            {AGENTS.map((agent) => (
              <div key={agent.id} className={styles.agentCard} style={{ '--agent-color': agent.color } as React.CSSProperties}>
                <div className={styles.agentHeader}>
                  <span className={styles.agentBadge} style={{ background: agent.color }}>
                    {agent.badge}
                  </span>
                  <div>
                    <div className={styles.agentName}>{agent.name}</div>
                    <div className={styles.agentPersona}>{agent.persona} · Port {agent.port}</div>
                  </div>
                </div>

                <p className={styles.agentDesc}>{agent.description}</p>

                <div className={styles.agentSection}>
                  <div className={styles.agentSubLabel}>DSPy Signatures</div>
                  <div className={styles.sigList}>
                    {agent.signatures.map((s) => (
                      <span key={s} className={styles.sigTag} style={{ borderColor: `${agent.color}44` }}>
                        {s}
                      </span>
                    ))}
                  </div>
                </div>

                <div className={styles.agentSection}>
                  <div className={styles.agentSubLabel}>RAG Sources</div>
                  <div className={styles.ragTags}>
                    {agent.ragTypes.map((t) => (
                      <span key={t} className={styles.ragTag}>{t}</span>
                    ))}
                  </div>
                </div>

                <div className={styles.agentDataDir}>
                  <Database size={11} />
                  <code>{agent.dataSource}</code>
                </div>
              </div>
            ))}
          </div>

          <div className={styles.siloNote}>
            <Shield size={14} className={styles.siloIcon} />
            <div>
              <strong>Federated RAG — Cognitive Silos</strong>
              <p>
                Each agent's ChromaDB collection enforces <code>SILO_ALLOWED_TYPES</code> — a domain-restricted
                allowlist of document metadata types. Documents with non-allowlisted <code>source_type</code> or{' '}
                <code>data_type</code> values are silently rejected at index time. Cross-silo queries are
                architecturally impossible; only the Governance Agent synthesises across domains.
                This preserves information provenance and prevents hallucination bleed between domains.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── FLOW TAB ───────────────────────────────────── */}
      {activeTab === 'flow' && (
        <div className={styles.tabContent}>
          <div className={styles.flowIntro}>
            Maximum <strong>4 rounds</strong> of multi-agent dialogue. Terminates on: confidence ≥ 0.8,
            all agents consulted, max rounds reached, or user clarification needed.
            Specialists always called <strong>in parallel</strong> via <code>asyncio.gather()</code>.
          </div>

          <div className={styles.flowList}>
            {FLOW_STEPS.map((step, i) => (
              <div key={i} className={styles.flowStep}>
                <div className={styles.flowLeft}>
                  <div className={styles.flowIndex}>{i + 1}</div>
                  {i < FLOW_STEPS.length - 1 && <div className={styles.flowLine} />}
                </div>
                <div className={styles.flowRight}>
                  <div className={styles.flowHeader}>
                    <span className={styles.flowLabel}>{step.label}</span>
                    {step.agent && (
                      <span
                        className={styles.flowAgent}
                        style={{ background: `${step.color}22`, color: step.color }}
                      >
                        {step.agent}
                      </span>
                    )}
                    {step.label === 'Specialist delegation (parallel)' && (
                      <span className={styles.parallelBadge}>⟳ parallel</span>
                    )}
                  </div>
                  <div className={styles.flowDetail}>{step.detail}</div>
                  <div className={styles.flowCode}><code>{step.code}</code></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── PROTOCOL TAB ───────────────────────────────── */}
      {activeTab === 'protocol' && (
        <div className={styles.tabContent}>
          <div className={styles.protocolIntro}>
            Every inter-agent message is a structured <strong>AgentCard</strong> — a JSON-LD-inspired schema
            with typed fields for routing, intent, confidence, and autonomy protocol.
            The <code>response_type</code> field is the core of the autonomy protocol and determines
            what the orchestrator does next.
          </div>

          <div className={styles.sectionTitle}><GitMerge size={14} /> The 6 Response States</div>
          <div className={styles.responseGrid}>
            {RESPONSE_TYPES.map((rt) => (
              <div key={rt.type} className={styles.responseCard} style={{ '--rt-color': rt.color } as React.CSSProperties}>
                <div className={styles.responseHeader}>
                  <DiffBadge label={rt.type} color={rt.color} />
                </div>
                <p className={styles.responseDesc}>{rt.description}</p>
                <div className={styles.responseMeta}>
                  <div className={styles.responseRow}>
                    <span className={styles.responseMetaLabel}>Trigger</span>
                    <span>{rt.trigger}</span>
                  </div>
                  <div className={styles.responseRow}>
                    <span className={styles.responseMetaLabel}>Outcome</span>
                    <span>{rt.outcome}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className={styles.sectionTitle} style={{ marginTop: '2rem' }}><Cpu size={14} /> AgentCard Schema</div>
          <div className={styles.schemaBox}>
            <div className={styles.schemaGrid}>
              {[
                ['message_id', 'string', 'UUID — unique message identifier'],
                ['correlation_id', 'string?', 'Links request ↔ response cards'],
                ['sender / recipient', 'AgentRole', 'governance_agent | hardware_agent | telemetry_agent'],
                ['intent', 'IntentType', 'QUERY | DIAGNOSE | VALIDATE | REPORT | DELEGATE | ESCALATE'],
                ['priority', 'Priority', 'LOW | NORMAL | HIGH | CRITICAL'],
                ['payload', 'Dict', 'Flexible: query, context, diagnosis, findings…'],
                ['documents', 'DocumentReference[]', 'Retrieved docs with relevance_score (0–1)'],
                ['confidence', 'float', '0.0–1.0 — agent\'s self-assessed confidence'],
                ['response_type', 'ResponseType', 'ANSWER | PARTIAL | CLARIFY | REDIRECT | REFUSE | CONSULT'],
                ['suggested_agent', 'AgentRole?', 'Set on CONSULT / REDIRECT — next agent to call'],
              ].map(([field, type, desc]) => (
                <div key={field} className={styles.schemaRow}>
                  <code className={styles.schemaField}>{field}</code>
                  <span className={styles.schemaType}>{type}</span>
                  <span className={styles.schemaDesc}>{desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── GRAPH TAB ──────────────────────────────────── */}
      {activeTab === 'graph' && (
        <div className={styles.tabContent}>
          <div className={styles.protocolIntro}>
            Neo4j knowledge graph enriches vector RAG with <strong>structured causal reasoning</strong>.
            When an error code is detected in a query, the graph service walks fault→event→SLA paths
            to surface related failures, resolution procedures, and SLA breach history.
          </div>

          <div className={styles.graphTwoCol}>
            <div>
              <div className={styles.sectionTitle}><Database size={14} /> Node Types (7 primary)</div>
              <div className={styles.nodeList}>
                {NEO4J_NODES.map((n) => (
                  <div key={n.name} className={styles.nodeCard}>
                    <div className={styles.nodeName}>{n.name}</div>
                    <div className={styles.nodeProps}><code>{n.props}</code></div>
                    <div className={styles.nodeExample}>{n.example}</div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className={styles.sectionTitle}><ArrowRight size={14} /> Relationship Types</div>
              <div className={styles.relList}>
                {NEO4J_RELS.map((r) => (
                  <div key={r.rel} className={styles.relRow}>
                    <code className={styles.relName}>{r.rel}</code>
                    <span className={styles.relDesc}>{r.desc}</span>
                  </div>
                ))}
              </div>

              <div className={styles.graphUsage}>
                <div className={styles.sectionTitle}><Brain size={14} /> Runtime Usage</div>
                <div className={styles.usageBox}>
                  <p>1. Governance agent calls <code>graph_service.get_enriched_context(query, location)</code></p>
                  <p>2. Error codes extracted from query via regex</p>
                  <p>3. Graph walks: <code>Fault → CAUSES → Event → VIOLATES → SLA</code></p>
                  <p>4. Returns fault path + station history + related errors + resolutions</p>
                  <p>5. Graph context appended to vector store context before DSPy reasoning</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── STACK TAB ──────────────────────────────────── */}
      {activeTab === 'stack' && (
        <div className={styles.tabContent}>
          <div className={styles.stackTable}>
            {TECH_STACK.map(({ layer, value }) => (
              <div key={layer} className={styles.stackRow}>
                <span className={styles.stackLayer}>{layer}</span>
                <span className={styles.stackValue}>{value}</span>
              </div>
            ))}
          </div>

          <div className={styles.modelTierBox}>
            <div className={styles.sectionTitle} style={{ marginBottom: '1rem' }}><Cpu size={14} /> Three-Tier Model Strategy</div>
            <div className={styles.tierGrid}>
              {[
                { tier: 'Tier 1', name: 'Router', model: 'GPT-4.1 (Azure)', temp: '0.0', role: 'Intent classification via EvaluateRequest. Deterministic — no creative variation.', color: '#60A5FA' },
                { tier: 'Tier 2', name: 'Reasoner', model: 'Claude Haiku 4.5 (Azure)', temp: '0.1', role: 'Global default for all three agent brains. Fast DSPy ChainOfThought reasoning.', color: '#F5A623' },
                { tier: 'Tier 3', name: 'Judge / Synthesiser', model: 'Claude Sonnet 4.5 (Azure)', temp: '0.1', role: 'Cross-domain synthesis (DiagnosisSynthesizer) + LLM-as-judge evaluation scoring.', color: '#4ADE80' },
              ].map((t) => (
                <div key={t.tier} className={styles.tierCard} style={{ '--tier-color': t.color } as React.CSSProperties}>
                  <div className={styles.tierHeader}>
                    <span className={styles.tierLabel} style={{ color: t.color }}>{t.tier}</span>
                    <span className={styles.tierName}>{t.name}</span>
                    <span className={styles.tierTemp}>temp {t.temp}</span>
                  </div>
                  <code className={styles.tierModel}>{t.model}</code>
                  <p className={styles.tierRole}>{t.role}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
