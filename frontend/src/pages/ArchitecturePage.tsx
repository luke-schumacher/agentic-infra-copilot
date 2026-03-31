import { Network, Database, Brain, ArrowRight, Layers } from 'lucide-react';
import styles from './ArchitecturePage.module.css';

interface AgentDef {
  id: string;
  name: string;
  persona: string;
  port: number;
  color: string;
  iconLabel: string;
  description: string;
  dataSource: string;
  ragTypes: string[];
}

const AGENTS: AgentDef[] = [
  {
    id: 'governance',
    name: 'Governance Agent',
    persona: 'The Anthropologist',
    port: 8001,
    color: '#60A5FA',
    iconLabel: 'GOV',
    description:
      'Workflow orchestrator and context manager. Routes queries, delegates to specialists, and synthesises cross-domain responses using SLA contracts, institutional policies, and maintenance schedules.',
    dataSource: 'data/processed/governance',
    ragTypes: ['SLA contracts', 'Institutional policies', 'Workflow logs', 'Maintenance records'],
  },
  {
    id: 'hardware',
    name: 'Hardware Agent',
    persona: 'The Specialist',
    port: 8002,
    color: '#F5A623',
    iconLabel: 'HW',
    description:
      'Technical diagnostic specialist for MRI hardware. Analyses DICOM conformance data, failure modes, error profiles, and operator manuals to diagnose scanner faults.',
    dataSource: 'data/processed/hardware',
    ragTypes: ['DICOM conformance', 'Failure modes', 'Error profiles', 'Operator manuals', 'DCS documentation'],
  },
  {
    id: 'telemetry',
    name: 'Telemetry Agent',
    persona: 'The Auditor',
    port: 8003,
    color: '#4ADE80',
    iconLabel: 'TEL',
    description:
      'Safety and compliance auditor. Cross-references safety zone definitions, personnel requirements, MRI SOPs, and ACR appropriateness criteria against event telemetry.',
    dataSource: 'data/processed/telemetry',
    ragTypes: ['Safety zones I–IV', 'Personnel requirements', 'MRI SOP', 'ACR criteria', 'Safety event flags'],
  },
];

const TECH_STACK = [
  { layer: 'LLM Framework', value: 'DSPy ChainOfThought' },
  { layer: 'Router model', value: 'GPT-4.1 (Azure) — temp 0.0' },
  { layer: 'Reasoner model', value: 'Claude Haiku 4.5 (Azure) — all agent brains' },
  { layer: 'Judge / Synthesiser', value: 'Claude Sonnet 4.5 (Azure) — eval + synthesis' },
  { layer: 'Vector store', value: 'ChromaDB — federated silos per agent' },
  { layer: 'Embedding model', value: 'text-embedding-3-small (OpenAI)' },
  { layer: 'Knowledge graph', value: 'Neo4j 5.15 (APOC)' },
  { layer: 'Serving framework', value: 'FastAPI (Python 3.11)' },
  { layer: 'Frontend', value: 'React 18 + Vite + TypeScript' },
  { layer: 'Deployment', value: 'Docker Compose (5 services)' },
];

const FLOW_STEPS = [
  {
    label: 'User query',
    detail:
      'Via React chat interface; includes optional context (customer_id, scanner_model, institution_type)',
  },
  {
    label: 'Governance Agent',
    detail:
      'Classifies intent via GPT-4.1 router, retrieves governance RAG context, decides whether to delegate',
  },
  {
    label: 'Specialist delegation',
    detail:
      'Hardware and/or Telemetry agents consulted in parallel via A2A Agent Cards (JSON-LD)',
  },
  {
    label: 'Parallel reasoning',
    detail:
      'Each specialist queries its own ChromaDB silo and Neo4j, runs DSPy ChainOfThought with Haiku',
  },
  {
    label: 'Cross-domain synthesis',
    detail:
      'Governance agent synthesises specialist findings with Claude Sonnet 4.5 into a unified diagnosis',
  },
  {
    label: 'Response',
    detail:
      'Structured AgentCard returned with confidence score, risk level, recommended actions, and source documents',
  },
];

export function ArchitecturePage() {
  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerTitle}>
          <Network size={20} />
          System Architecture
        </div>
        <div className={styles.headerMeta}>
          Tripartite Multi-Agent System for MRI infrastructure diagnostics
        </div>
      </div>

      {/* Agent cards */}
      <section className={styles.section}>
        <div className={styles.sectionTitle}>
          <Brain size={14} />
          Agent Roles
        </div>
        <div className={styles.agentGrid}>
          {AGENTS.map((agent) => (
            <div
              key={agent.id}
              className={styles.agentCard}
              style={{ '--agent-color': agent.color } as React.CSSProperties}
            >
              <div className={styles.agentHeader}>
                <span className={styles.agentBadge} style={{ background: agent.color }}>
                  {agent.iconLabel}
                </span>
                <div>
                  <div className={styles.agentName}>{agent.name}</div>
                  <div className={styles.agentPersona}>
                    {agent.persona} · Port {agent.port}
                  </div>
                </div>
              </div>
              <p className={styles.agentDesc}>{agent.description}</p>
              <div className={styles.agentRag}>
                <span className={styles.ragLabel}>RAG sources:</span>
                <div className={styles.ragTags}>
                  {agent.ragTypes.map((t) => (
                    <span key={t} className={styles.ragTag}>
                      {t}
                    </span>
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
      </section>

      {/* Query flow */}
      <section className={styles.section}>
        <div className={styles.sectionTitle}>
          <ArrowRight size={14} />
          Query Flow
        </div>
        <div className={styles.flowList}>
          {FLOW_STEPS.map((step, i) => (
            <div key={i} className={styles.flowStep}>
              <div className={styles.flowIndex}>{i + 1}</div>
              <div className={styles.flowContent}>
                <div className={styles.flowLabel}>{step.label}</div>
                <div className={styles.flowDetail}>{step.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Tech stack */}
      <section className={styles.section}>
        <div className={styles.sectionTitle}>
          <Layers size={14} />
          Technology Stack
        </div>
        <div className={styles.stackTable}>
          {TECH_STACK.map(({ layer, value }) => (
            <div key={layer} className={styles.stackRow}>
              <span className={styles.stackLayer}>{layer}</span>
              <span className={styles.stackValue}>{value}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Federated RAG note */}
      <section className={styles.section}>
        <div className={styles.sectionTitle}>
          <Database size={14} />
          Federated Agentic RAG
        </div>
        <div className={styles.ragNote}>
          <p>
            Each agent maintains an <strong>isolated ChromaDB silo</strong> enforced by{' '}
            <code>SILO_ALLOWED_TYPES</code> — a domain-restricted allowlist of document metadata
            types. Cross-silo queries are impossible by design; only the orchestrating Governance
            Agent can synthesise across domains. This preserves information provenance and prevents
            hallucination bleed.
          </p>
          <p>
            PDFs are chunked with <code>RecursiveCharacterTextSplitter</code> (chunk_size=1000,
            overlap=200) via LangChain. The hardware silo indexes operator manuals and DCS
            documentation; the telemetry silo indexes MRI SOPs and ACR safety criteria.
          </p>
        </div>
      </section>
    </div>
  );
}
