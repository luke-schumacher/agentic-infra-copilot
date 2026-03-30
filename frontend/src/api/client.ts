import type { AgentHealthStatus, ConsultRequest, ConsultResponse, QueryContext, AgentCard } from '../types';

function timeout(ms: number): Promise<never> {
  return new Promise((_, reject) => setTimeout(() => reject(new Error(`timeout:${ms}`)), ms));
}

function normalizeError(err: unknown): string {
  if (err instanceof Error) {
    if (err.message.startsWith('timeout:')) return 'Request timed out — agents may be busy';
    if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
      return 'Cannot connect — ensure backend is running';
    }
    return err.message;
  }
  return String(err);
}

async function safeFetch(url: string, options: RequestInit, ms: number): Promise<Response> {
  return Promise.race([fetch(url, options), timeout(ms)]);
}

export async function checkHealth(agentUrl: string): Promise<AgentHealthStatus> {
  try {
    const res = await safeFetch(`${agentUrl}/health`, {}, 5000);
    if (!res.ok) return { status: 'unhealthy', error: `HTTP ${res.status}` };
    return res.json();
  } catch (e) {
    return { status: 'unhealthy', error: normalizeError(e) };
  }
}

export async function consultAgent(query: string, context: QueryContext): Promise<ConsultResponse> {
  const card: AgentCard = {
    sender: 'orchestrator',
    recipient: 'governance_agent',
    intent: context.query_type === 'symptom' ? 'diagnose' : 'query',
    priority: context.query_type === 'symptom' ? 'high' : 'normal',
    payload: {
      query,
      customer_id: context.customer_id || undefined,
      scanner_model: context.scanner_model || undefined,
      institution_type: context.institution_type || undefined,
      location: context.location || undefined,
      is_symptom: context.query_type === 'symptom',
    },
  };
  const body: ConsultRequest = { card };
  try {
    const res = await safeFetch('/api/gov/consult', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }, 180000);
    if (!res.ok) {
      const t = await res.text().catch(() => '');
      throw new Error(`HTTP ${res.status}: ${t}`);
    }
    return res.json();
  } catch (e) {
    return { success: false, error: normalizeError(e) };
  }
}

export async function indexDocuments(agentUrl: string): Promise<{ indexed_count: number; error?: string }> {
  try {
    const res = await safeFetch(`${agentUrl}/index`, { method: 'POST' }, 120000);
    if (!res.ok) {
      const t = await res.text().catch(() => '');
      throw new Error(`HTTP ${res.status}: ${t}`);
    }
    return res.json();
  } catch (e) {
    return { indexed_count: 0, error: normalizeError(e) };
  }
}
