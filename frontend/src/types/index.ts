export interface AgentHealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  document_count?: number;
  dspy_ready?: boolean;
  vector_store_ready?: boolean;
  uptime_seconds?: number;
  error?: string;
}

export type DisplayStatus = 'ok' | 'warn' | 'err' | 'unknown';

export function toDisplayStatus(s?: string): DisplayStatus {
  if (s === 'healthy') return 'ok';
  if (s === 'degraded') return 'warn';
  if (s === 'unhealthy') return 'err';
  return 'unknown';
}

export interface AgentInfo {
  id: 'gov' | 'hw' | 'tel';
  name: string;
  port: number;
  url: string;
}

export const AGENTS: AgentInfo[] = [
  { id: 'gov', name: 'Governance', port: 8001, url: '/api/gov' },
  { id: 'hw',  name: 'Hardware',   port: 8002, url: '/api/hw'  },
  { id: 'tel', name: 'Telemetry',  port: 8003, url: '/api/tel' },
];

export interface DocumentReference {
  source: string;
  file_name?: string;
  content_snippet?: string;
  relevance_score?: number;
  metadata?: Record<string, unknown>;
}

export interface AgentCardPayload {
  query?: string;
  customer_id?: string;
  scanner_model?: string;
  institution_type?: string;
  location?: string;
  is_symptom?: boolean;
  contextual_explanation?: string;
  answer?: string;
  risk_level?: string;
  recommended_actions?: string | string[];
  confidence_score?: number;
  specialist_findings?: unknown;
  delegation?: { target_agent?: string; reason?: string } | unknown;
  [key: string]: unknown;
}

export interface AgentCard {
  sender?: string;
  recipient?: string;
  intent?: string;
  priority?: string;
  payload?: AgentCardPayload;
  confidence?: number;
  response_type?: 'ANSWER' | 'PARTIAL' | 'CLARIFY' | 'REDIRECT' | 'REFUSE' | 'CONSULT' | string;
  documents?: DocumentReference[];
  [key: string]: unknown;
}

export interface ConsultRequest {
  card: AgentCard;
}

export interface ConsultResponse {
  success: boolean;
  error?: string;
  processing_time_ms?: number;
  response_card?: AgentCard;
}

export interface SpecialistFindings {
  agent: string;
  response_card?: AgentCard;
  processing_time_ms?: number;
}

export interface ReasoningRound {
  round_number: number;
  agent: string;
  response_type?: string;
  confidence?: number;
}

export interface QueryContext {
  customer_id: string;
  scanner_model: string;
  institution_type: string;
  location: string;
  query_type: 'symptom' | 'general';
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: DocumentReference[];
  delegation?: string[];
  specialistFindings?: SpecialistFindings[];
  reasoning?: ReasoningRound[];
  riskLevel?: string;
  confidence?: number;
  responseType?: string;
  processingTimeMs?: number;
  isPartial?: boolean;
  error?: string;
}

// ---------------------------------------------------------------------------
// Evaluation types
// ---------------------------------------------------------------------------

export interface AblationResult {
  mode: string;
  accuracy_score: number;
  confidence: number;
  keyword_matches: number;
  total_keywords: number;
  judge_scores?: Record<string, number>;
  semantic_score?: number;
  emergence_detected: boolean;
  cross_domain_refs: number;
  latency_ms: number;
}

export interface AblationComparison {
  test_case_name: string;
  test_case_difficulty: string;
  results: Record<string, AblationResult>;
  mas_accuracy: number;
  best_single_agent_accuracy: number;
  emergence_margin: number;
  emergence_demonstrated: boolean;
}

export interface EvalRunProgress {
  completed: number;
  total: number;
  current_test_case: string;
  current_mode: string;
  percentage: number;
}

export interface EvalRunStatus {
  run_id: string;
  status: 'running' | 'completed' | 'failed';
  started_at: string;
  error?: string;
  progress: EvalRunProgress;
  comparisons: AblationComparison[];
  thesis_summary?: Record<string, unknown>;
}

export interface AgentDataStatus {
  name: string;
  port: number;
  status: string;
  document_count: number;
  dspy_ready: boolean;
  vector_store_ready: boolean;
  error?: string;
}

/** Extract display text from an AgentCard payload */
export function extractContent(card?: AgentCard): string {
  if (!card) return '';
  const p = card.payload;
  if (!p) return '';
  if (p.contextual_explanation) return String(p.contextual_explanation);
  if (p.answer) return String(p.answer);
  // Fallback: collect non-input fields
  const skip = new Set(['query', 'customer_id', 'scanner_model', 'institution_type', 'location', 'is_symptom']);
  return Object.entries(p)
    .filter(([k, v]) => !skip.has(k) && v !== null && v !== undefined && typeof v !== 'object')
    .map(([k, v]) => `${k}: ${v}`)
    .join('\n');
}

/** Extract specialist findings from response card payload */
export function extractSpecialistFindings(card?: AgentCard): SpecialistFindings[] {
  const raw = card?.payload?.specialist_findings;
  if (!raw) return [];
  if (Array.isArray(raw)) return raw as SpecialistFindings[];
  if (typeof raw === 'object') return [raw as SpecialistFindings];
  return [];
}

/** Extract delegation chain from response card payload */
export function extractDelegation(card?: AgentCard): string[] {
  const d = card?.payload?.delegation;
  if (!d) return [];
  if (Array.isArray(d)) return d as string[];
  if (typeof d === 'object' && d !== null) {
    const target = (d as Record<string, unknown>).target_agent;
    if (target) return [String(target)];
  }
  if (typeof d === 'string') return [d];
  return [];
}
