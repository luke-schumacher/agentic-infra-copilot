import type { AblationComparison, EvalRunStatus, AgentDataStatus } from '../types';

const GOV = '/api/gov';

export interface EvalStartRequest {
  test_cases?: string[];
  no_resume?: boolean;
}

export interface EvalStartResponse {
  run_id: string;
  total_evaluations: number;
}

export async function startEvaluation(request: EvalStartRequest = {}): Promise<EvalStartResponse> {
  const res = await fetch(`${GOV}/evaluation/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

export async function getEvalStatus(runId: string): Promise<EvalRunStatus> {
  const res = await fetch(`${GOV}/evaluation/status/${runId}`);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

export async function getEvalResults(): Promise<AblationComparison[]> {
  const res = await fetch(`${GOV}/evaluation/results`);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

export async function getDataStatus(): Promise<AgentDataStatus[]> {
  const res = await fetch(`${GOV}/evaluation/data-status`);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}
