/**
 * Static thesis result data for display in the Results and Research pages.
 * Sourced from evaluation runs; updated after each complete run.
 */

export interface ModeResult {
  mode: string;
  label: string;
  avg_accuracy: number;
  avg_relevance: number;
  avg_completeness: number;
  avg_cross_domain: number;
  avg_overall: number;
  pass_rate: number;
  cases_evaluated: number;
}

export interface RunSummary {
  run_id: string;
  label: string;
  date: string;
  cases: number;
  notes: string;
  mas_overall: number;
  best_single_overall: number;
  emergence_rate: number;
}

export interface EmergenceCase {
  name: string;
  difficulty: 'simple' | 'moderate' | 'complex';
  mas_score: number;
  best_single_score: number;
  margin: number;
  domain_synergy: string;
}

// ---------------------------------------------------------------------------
// Run 2 pilot results (12 cases × 5 modes = 60 evaluations)
// ---------------------------------------------------------------------------

export const MODE_RESULTS: ModeResult[] = [
  {
    mode: 'mas_full',
    label: 'MAS (Full)',
    avg_accuracy: 0.74,
    avg_relevance: 0.79,
    avg_completeness: 0.71,
    avg_cross_domain: 0.82,
    avg_overall: 0.76,
    pass_rate: 0.83,
    cases_evaluated: 12,
  },
  {
    mode: 'single_all_data',
    label: 'Single + All Data',
    avg_accuracy: 0.61,
    avg_relevance: 0.72,
    avg_completeness: 0.58,
    avg_cross_domain: 0.54,
    avg_overall: 0.61,
    pass_rate: 0.58,
    cases_evaluated: 12,
  },
  {
    mode: 'governance_only',
    label: 'Governance Only',
    avg_accuracy: 0.52,
    avg_relevance: 0.65,
    avg_completeness: 0.49,
    avg_cross_domain: 0.31,
    avg_overall: 0.50,
    pass_rate: 0.42,
    cases_evaluated: 12,
  },
  {
    mode: 'hardware_only',
    label: 'Hardware Only',
    avg_accuracy: 0.58,
    avg_relevance: 0.68,
    avg_completeness: 0.55,
    avg_cross_domain: 0.28,
    avg_overall: 0.53,
    pass_rate: 0.50,
    cases_evaluated: 12,
  },
  {
    mode: 'telemetry_only',
    label: 'Telemetry Only',
    avg_accuracy: 0.44,
    avg_relevance: 0.61,
    avg_completeness: 0.41,
    avg_cross_domain: 0.22,
    avg_overall: 0.43,
    pass_rate: 0.33,
    cases_evaluated: 12,
  },
];

export const RUN_SUMMARIES: RunSummary[] = [
  {
    run_id: 'run-1',
    label: 'Run 1 – Initial pilot',
    date: '2026-01-30',
    cases: 6,
    notes: 'Development pilot; 6 cases, early routing logic. Not used for evaluation.',
    mas_overall: 0.68,
    best_single_overall: 0.55,
    emergence_rate: 0.50,
  },
  {
    run_id: 'run-2',
    label: 'Run 2 – Pilot 12-case',
    date: '2026-03-15',
    cases: 12,
    notes: 'Full 12-case ablation with rate-limit fixes. Baseline for comparison.',
    mas_overall: 0.76,
    best_single_overall: 0.61,
    emergence_rate: 0.75,
  },
  {
    run_id: 'run-3',
    label: 'Run 3 – Primary evaluation (pending)',
    date: '–',
    cases: 12,
    notes: 'Primary thesis run with operator manual + safety PDF data. Azure Sonnet-4.5 judge.',
    mas_overall: 0,
    best_single_overall: 0,
    emergence_rate: 0,
  },
];

export const EMERGENCE_CASES: EmergenceCase[] = [
  {
    name: 'cascading_thermal_fault',
    difficulty: 'moderate',
    mas_score: 0.82,
    best_single_score: 0.61,
    margin: 0.21,
    domain_synergy: 'Hardware fault codes + Governance SLA + Telemetry event pattern',
  },
  {
    name: 'phantom_load_spike',
    difficulty: 'complex',
    mas_score: 0.79,
    best_single_score: 0.58,
    margin: 0.21,
    domain_synergy: 'Hardware sensor data + Telemetry anomaly flags',
  },
  {
    name: 'helium_boiloff_cascade',
    difficulty: 'complex',
    mas_score: 0.77,
    best_single_score: 0.54,
    margin: 0.23,
    domain_synergy: 'Hardware specs + Governance maintenance schedule + Telemetry boiloff events',
  },
  {
    name: 'gradient_coil_degradation',
    difficulty: 'complex',
    mas_score: 0.75,
    best_single_score: 0.60,
    margin: 0.15,
    domain_synergy: 'Hardware diagnostics + Telemetry gradient error events',
  },
  {
    name: 'missed_maintenance_escalation',
    difficulty: 'simple',
    mas_score: 0.88,
    best_single_score: 0.71,
    margin: 0.17,
    domain_synergy: 'Governance SLA policy + Hardware maintenance records',
  },
  {
    name: 'protocol_conflict_sla',
    difficulty: 'moderate',
    mas_score: 0.80,
    best_single_score: 0.63,
    margin: 0.17,
    domain_synergy: 'Governance SLA + Telemetry safety compliance checks',
  },
  {
    name: 'multi_scanner_cooling',
    difficulty: 'complex',
    mas_score: 0.73,
    best_single_score: 0.59,
    margin: 0.14,
    domain_synergy: 'Hardware cooling specs + Telemetry temperature trends + Governance scheduling',
  },
  {
    name: 'shimming_environmental',
    difficulty: 'complex',
    mas_score: 0.71,
    best_single_score: 0.57,
    margin: 0.14,
    domain_synergy: 'Hardware shimming data + Telemetry environmental flags',
  },
  {
    name: 'software_update_regression',
    difficulty: 'moderate',
    mas_score: 0.76,
    best_single_score: 0.64,
    margin: 0.12,
    domain_synergy: 'Hardware firmware logs + Governance change management',
  },
];

// Run 3 placeholder — will be populated after primary evaluation
export const MAS_JUDGE_SCORES_RUN3: Record<string, number> = {};

export const DIFFICULTY_BREAKDOWN = {
  simple:   { count: 2, mas_avg: 0.84, single_avg: 0.68 },
  moderate: { count: 5, mas_avg: 0.79, single_avg: 0.63 },
  complex:  { count: 5, mas_avg: 0.71, single_avg: 0.57 },
};
