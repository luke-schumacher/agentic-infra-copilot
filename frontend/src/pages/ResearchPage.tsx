import { FlaskConical, BookOpen, Target, CheckCircle, Circle } from 'lucide-react';
import styles from './ResearchPage.module.css';

interface ResearchSection {
  id: string;
  title: string;
  content: string[];
}

const RESEARCH_OVERVIEW: ResearchSection[] = [
  {
    id: 'problem',
    title: 'Problem Statement',
    content: [
      'MRI infrastructure management in radiology departments involves complex, multi-domain decision-making spanning hardware diagnostics, safety compliance, and institutional governance. Current approaches rely on isolated specialist knowledge with no systematic cross-domain synthesis.',
      'This thesis investigates whether a tripartite Multi-Agent System (MAS), with domain-specialised agents and federated knowledge bases, can demonstrably outperform single-agent baselines through emergent cross-domain reasoning.',
    ],
  },
  {
    id: 'hypothesis',
    title: 'Research Hypothesis',
    content: [
      'H1: A tripartite MAS with domain-specialised agents and federated RAG will achieve higher diagnostic accuracy on complex, cross-domain MRI infrastructure queries than any single-agent baseline — including a single agent given access to all data (Single+All).',
      'H2: The performance advantage of MAS will be most pronounced for queries requiring synthesis across two or more domains (complex difficulty), where no single specialist can provide a complete diagnosis.',
    ],
  },
  {
    id: 'methodology',
    title: 'Methodology',
    content: [
      'Ablation study design: 5 modes × 12 standardised test cases = 60 evaluated responses per run. Modes: governance_only, hardware_only, telemetry_only, single_all_data, mas_full.',
      'Evaluation uses an LLM-as-judge (Claude Sonnet 4.5) with four metrics: accuracy (weight 0.35), relevance (0.20), completeness (0.20), cross-domain synthesis (0.25). Pass threshold: 0.60.',
      'Test cases span three difficulty levels (simple, moderate, complex) and cover failure scenarios including cascading thermal faults, helium boil-off cascades, gradient coil degradation, and multi-scanner cooling events.',
      'Ground truth responses were manually authored for each test case by the researcher using Siemens Healthineers domain knowledge and ACR safety standards.',
    ],
  },
];

const RESEARCH_QUESTIONS = [
  'RQ1: Does MAS emergence — where MAS accuracy exceeds best single-agent — occur for complex cross-domain queries?',
  'RQ2: Does federated RAG (domain-restricted silos) improve diagnostic accuracy over a unified single-agent RAG store?',
  'RQ3: What is the role of the cross-domain synthesis step (Sonnet) in the overall performance gain?',
  'RQ4: How does query difficulty (simple/moderate/complex) moderate MAS advantage?',
];

const CONTRIBUTIONS = [
  'Design and implementation of a production-ready tripartite MAS for MRI infrastructure diagnostics',
  'Novel federated Agentic RAG architecture with domain-enforced SILO_ALLOWED_TYPES constraints',
  'Three-tier model strategy using DSPy: GPT-4.1 router, Claude Haiku reasoner, Claude Sonnet judge/synthesiser',
  'Empirical ablation study measuring emergence in multi-agent LLM systems',
  'Integration of Siemens Healthineers real-world data (DICOM, event logs, operator manuals, safety SOPs)',
  'Open-source implementation with Docker Compose deployment and React evaluation frontend',
];

const LIMITATIONS = [
  'Ground truth authored by a single researcher — potential for expert bias',
  'LLM-as-judge evaluation introduces model-specific scoring patterns',
  'Test case coverage limited to 12 scenarios (expanded in Run 3)',
  'Azure rate limits constrain parallelism in large evaluation runs',
  'Patient data fully de-identified; real-world deployment would require additional compliance review',
];

export function ResearchPage() {
  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerTitle}>
          <FlaskConical size={20} />
          Research Context
        </div>
        <div className={styles.headerMeta}>
          MSc thesis — Agentic Infrastructure Co-Pilot for MRI Diagnostics
        </div>
      </div>

      {/* Overview sections */}
      {RESEARCH_OVERVIEW.map((section) => (
        <section key={section.id} className={styles.section}>
          <div className={styles.sectionTitle}>
            <BookOpen size={14} />
            {section.title}
          </div>
          <div className={styles.prose}>
            {section.content.map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
        </section>
      ))}

      {/* Research questions */}
      <section className={styles.section}>
        <div className={styles.sectionTitle}>
          <Target size={14} />
          Research Questions
        </div>
        <div className={styles.rqList}>
          {RESEARCH_QUESTIONS.map((rq, i) => (
            <div key={i} className={styles.rqItem}>
              <div className={styles.rqIndex}>RQ{i + 1}</div>
              <div className={styles.rqText}>{rq.replace(/^RQ\d+:\s*/, '')}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Contributions */}
      <section className={styles.section}>
        <div className={styles.sectionTitle}>
          <CheckCircle size={14} />
          Key Contributions
        </div>
        <div className={styles.checkList}>
          {CONTRIBUTIONS.map((c, i) => (
            <div key={i} className={styles.checkItem}>
              <CheckCircle size={13} className={styles.checkIcon} />
              <span>{c}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Limitations */}
      <section className={styles.section}>
        <div className={styles.sectionTitle}>
          <Circle size={14} />
          Limitations &amp; Future Work
        </div>
        <div className={styles.limitList}>
          {LIMITATIONS.map((l, i) => (
            <div key={i} className={styles.limitItem}>
              <span className={styles.limitDot} />
              <span>{l}</span>
            </div>
          ))}
        </div>
        <div className={styles.futureNote}>
          Future work includes multi-rater ground truth validation, real-time telemetry ingestion,
          and extension to other imaging modalities (CT, PET). The federated RAG architecture is
          generalisable to any multi-domain diagnostic system.
        </div>
      </section>
    </div>
  );
}
