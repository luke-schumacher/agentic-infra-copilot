import { useState, useEffect, useCallback, useRef } from 'react';
import { X, BarChart2, Play, RefreshCw, CheckSquare, Square } from 'lucide-react';
import styles from './EvaluationPanel.module.css';
import type { AblationComparison, AgentDataStatus, EvalRunStatus } from '../../types';
import {
  startEvaluation,
  getEvalStatus,
  getEvalResults,
  getDataStatus,
} from '../../api/evaluation';

// ---------------------------------------------------------------------------
// Static test case metadata (mirrors emergence_tests.py)
// ---------------------------------------------------------------------------

const TEST_CASES = [
  { name: 'cascading_thermal_fault',    difficulty: 'moderate' },
  { name: 'phantom_load_spike',         difficulty: 'complex'  },
  { name: 'gradient_coil_degradation',  difficulty: 'complex'  },
  { name: 'helium_boiloff_cascade',     difficulty: 'complex'  },
  { name: 'software_update_regression', difficulty: 'moderate' },
  { name: 'rf_amplifier_intermittent',  difficulty: 'moderate' },
  { name: 'missed_maintenance_escalation', difficulty: 'simple' },
  { name: 'network_false_alarm',        difficulty: 'moderate' },
  { name: 'protocol_conflict_sla',      difficulty: 'moderate' },
  { name: 'known_fault_code_lookup',    difficulty: 'simple'   },
  { name: 'shimming_environmental',     difficulty: 'complex'  },
  { name: 'multi_scanner_cooling',      difficulty: 'complex'  },
] as const;

const MODE_LABELS: Record<string, string> = {
  governance_only: 'Gov',
  hardware_only: 'HW',
  telemetry_only: 'Tel',
  single_all_data: 'Single+All',
  mas_full: 'MAS',
};

const MODES = ['governance_only', 'hardware_only', 'telemetry_only', 'single_all_data', 'mas_full'];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
  open: boolean;
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function DataStatusStrip({ statuses }: { statuses: AgentDataStatus[] }) {
  if (statuses.length === 0) {
    return <div className={styles.dataStatusLoading}>Checking agent status…</div>;
  }
  return (
    <div className={styles.dataStatusStrip}>
      {statuses.map((s) => {
        const ok = s.status === 'healthy';
        const warn = s.status === 'degraded';
        const dotCls = ok ? styles.dotOk : warn ? styles.dotWarn : styles.dotErr;
        const label = s.name.replace('_agent', '').replace('governance', 'Governance').replace('hardware', 'Hardware').replace('telemetry', 'Telemetry');
        return (
          <div key={s.name} className={styles.dataStatusCard}>
            <span className={`${styles.dot} ${dotCls}`} />
            <span className={styles.dataStatusLabel}>{label}</span>
            <span className={styles.dataStatusDocs}>{s.document_count} docs</span>
            <span className={styles.dataStatusBadge} data-status={s.status}>{s.status}</span>
          </div>
        );
      })}
    </div>
  );
}

function DifficultyBadge({ difficulty }: { difficulty: string }) {
  return (
    <span className={styles.diffBadge} data-difficulty={difficulty}>
      {difficulty}
    </span>
  );
}

function AccuracyCell({ value }: { value?: number }) {
  if (value === undefined || value === null) return <td className={styles.naCell}>—</td>;
  const pct = Math.round(value * 100);
  const cls = pct >= 70 ? styles.cellGood : pct >= 40 ? styles.cellMid : styles.cellBad;
  return <td className={`${styles.accuracyCell} ${cls}`}>{pct}%</td>;
}

function EmergenceCell({ demonstrated, margin }: { demonstrated: boolean; margin: number }) {
  const cls = demonstrated ? styles.emergenceYes : styles.emergenceNo;
  const sign = margin >= 0 ? '+' : '';
  return (
    <td className={`${styles.emergenceCell} ${cls}`}>
      {demonstrated ? 'YES' : 'no'}
      <span className={styles.margin}>{sign}{Math.round(margin * 100)}%</span>
    </td>
  );
}

function ResultsTable({ comparisons }: { comparisons: AblationComparison[] }) {
  if (comparisons.length === 0) return null;

  const emergenceCount = comparisons.filter((c) => c.emergence_demonstrated).length;
  const avgMas = comparisons.reduce((s, c) => s + c.mas_accuracy, 0) / comparisons.length;
  const avgBest = comparisons.reduce((s, c) => s + c.best_single_agent_accuracy, 0) / comparisons.length;

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.resultsTable}>
        <thead>
          <tr>
            <th>Test Case</th>
            <th>Diff</th>
            {MODES.map((m) => <th key={m}>{MODE_LABELS[m]}</th>)}
            <th>Emergence</th>
          </tr>
        </thead>
        <tbody>
          {comparisons.map((c) => (
            <tr key={c.test_case_name}>
              <td className={styles.caseNameCell} title={c.test_case_name}>
                {c.test_case_name.replace(/_/g, ' ')}
              </td>
              <td><DifficultyBadge difficulty={c.test_case_difficulty} /></td>
              {MODES.map((m) => (
                <AccuracyCell key={m} value={c.results[m]?.accuracy_score} />
              ))}
              <EmergenceCell
                demonstrated={c.emergence_demonstrated}
                margin={c.emergence_margin}
              />
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={2} className={styles.summaryLabel}>Avg</td>
            {MODES.map((m) => {
              const avg = comparisons.reduce((s, c) => s + (c.results[m]?.accuracy_score ?? 0), 0) / comparisons.length;
              return <td key={m} className={styles.summaryCell}>{Math.round(avg * 100)}%</td>;
            })}
            <td className={styles.summaryCell}>
              <span className={styles.emergenceBadge}>{emergenceCount}/{comparisons.length}</span>
            </td>
          </tr>
        </tfoot>
      </table>
      <div className={styles.summaryRow}>
        <span>Avg MAS: <strong>{Math.round(avgMas * 100)}%</strong></span>
        <span>Avg Best Single: <strong>{Math.round(avgBest * 100)}%</strong></span>
        <span>Emergence: <strong>{emergenceCount}/{comparisons.length} cases</strong></span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export function EvaluationPanel({ open, onClose }: Props) {
  const [dataStatuses, setDataStatuses] = useState<AgentDataStatus[]>([]);
  const [selected, setSelected] = useState<Set<string>>(
    new Set(TEST_CASES.map((tc) => tc.name))
  );
  const [noResume, setNoResume] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<EvalRunStatus | null>(null);
  const [results, setResults] = useState<AblationComparison[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number | null>(null);

  const isRunning = runStatus?.status === 'running';

  // Load data status on mount
  useEffect(() => {
    if (!open) return;
    getDataStatus()
      .then(setDataStatuses)
      .catch((e) => console.warn('data-status failed:', e));
  }, [open]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (elapsedRef.current) clearInterval(elapsedRef.current);
    };
  }, []);

  // Poll while running
  useEffect(() => {
    if (!runId || !isRunning) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }
    const poll = async () => {
      try {
        const status = await getEvalStatus(runId);
        setRunStatus(status);
        if (status.status !== 'running') {
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
          if (elapsedRef.current) { clearInterval(elapsedRef.current); elapsedRef.current = null; }
          if (status.comparisons?.length) setResults(status.comparisons);
        }
      } catch (e) {
        console.warn('poll failed:', e);
      }
    };
    pollRef.current = setInterval(poll, 5000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [runId, isRunning]);

  const startElapsedTimer = useCallback(() => {
    startTimeRef.current = Date.now();
    setElapsed(0);
    if (elapsedRef.current) clearInterval(elapsedRef.current);
    elapsedRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - (startTimeRef.current ?? Date.now())) / 1000));
    }, 1000);
  }, []);

  const handleRun = useCallback(async () => {
    if (isRunning) return;
    setError(null);
    setResults([]);
    setRunStatus(null);
    try {
      const selectedList = Array.from(selected);
      const allSelected = selectedList.length === TEST_CASES.length;
      const resp = await startEvaluation({
        test_cases: allSelected ? undefined : selectedList,
        no_resume: noResume,
      });
      setRunId(resp.run_id);
      setRunStatus({
        run_id: resp.run_id,
        status: 'running',
        started_at: new Date().toISOString(),
        progress: {
          completed: 0,
          total: resp.total_evaluations,
          current_test_case: '',
          current_mode: '',
          percentage: 0,
        },
        comparisons: [],
      });
      startElapsedTimer();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [isRunning, selected, noResume, startElapsedTimer]);

  const handleLoadExisting = useCallback(async () => {
    try {
      const data = await getEvalResults();
      setResults(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const handleSelectAll = useCallback(() => {
    setSelected(new Set(TEST_CASES.map((tc) => tc.name)));
  }, []);

  const handleSelectNone = useCallback(() => {
    setSelected(new Set());
  }, []);

  const toggleCase = useCallback((name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }, []);

  const formatElapsed = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  if (!open) return null;

  const progress = runStatus?.progress;
  const displayedResults = results.length > 0 ? results : (runStatus?.comparisons ?? []);

  return (
    <div className={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={styles.panel}>
        {/* Header */}
        <div className={styles.panelHeader}>
          <div className={styles.panelTitle}>
            <BarChart2 size={18} />
            Evaluation Suite
          </div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close evaluation panel">
            <X size={18} />
          </button>
        </div>

        <div className={styles.panelBody}>
          {/* Data Status */}
          <section className={styles.section}>
            <div className={styles.sectionTitle}>
              Agent Data Readiness
              <button className={styles.iconBtn} onClick={() => getDataStatus().then(setDataStatuses)} title="Refresh">
                <RefreshCw size={13} />
              </button>
            </div>
            <DataStatusStrip statuses={dataStatuses} />
          </section>

          {/* Test Case Grid */}
          <section className={styles.section}>
            <div className={styles.sectionTitle}>
              Test Cases
              <span className={styles.sectionMeta}>{selected.size} / {TEST_CASES.length} selected</span>
              <button className={styles.linkBtn} onClick={handleSelectAll}>All</button>
              <button className={styles.linkBtn} onClick={handleSelectNone}>None</button>
            </div>
            <div className={styles.caseGrid}>
              {TEST_CASES.map((tc) => (
                <label key={tc.name} className={styles.caseLabel}>
                  <span className={styles.caseCheckbox} onClick={() => toggleCase(tc.name)}>
                    {selected.has(tc.name)
                      ? <CheckSquare size={14} className={styles.checked} />
                      : <Square size={14} className={styles.unchecked} />
                    }
                  </span>
                  <span className={styles.caseName}>{tc.name.replace(/_/g, ' ')}</span>
                  <DifficultyBadge difficulty={tc.difficulty} />
                </label>
              ))}
            </div>
          </section>

          {/* Run Controls */}
          <section className={styles.section}>
            <div className={styles.controls}>
              <label className={styles.toggleLabel}>
                <input
                  type="checkbox"
                  checked={!noResume}
                  onChange={(e) => setNoResume(!e.target.checked)}
                />
                Skip already-completed (resume)
              </label>
              <div className={styles.btnGroup}>
                <button
                  className={styles.runBtn}
                  onClick={handleRun}
                  disabled={isRunning || selected.size === 0}
                >
                  <Play size={14} />
                  {isRunning ? 'Running…' : 'Run Evaluation'}
                </button>
              </div>
            </div>
            {error && <div className={styles.errorMsg}>{error}</div>}
          </section>

          {/* Progress */}
          {(isRunning || runStatus?.status === 'completed') && progress && (
            <section className={styles.section}>
              <div className={styles.sectionTitle}>
                Progress
                {isRunning && <span className={styles.elapsedBadge}>{formatElapsed(elapsed)}</span>}
                {runStatus?.status === 'completed' && <span className={styles.completedBadge}>Completed</span>}
                {runStatus?.status === 'failed' && <span className={styles.failedBadge}>Failed</span>}
              </div>
              <div className={styles.progressBarWrap}>
                <div
                  className={styles.progressBar}
                  style={{ width: `${progress.percentage}%` }}
                />
              </div>
              <div className={styles.progressMeta}>
                <span>{progress.completed}/{progress.total} evaluations ({progress.percentage}%)</span>
                {progress.current_test_case && (
                  <span className={styles.currentCase}>
                    {progress.current_test_case.replace(/_/g, ' ')}
                    {progress.current_mode && ` → ${progress.current_mode}`}
                  </span>
                )}
              </div>
              {runStatus?.error && (
                <div className={styles.errorMsg}>Error: {runStatus.error}</div>
              )}
            </section>
          )}

          {/* Results Table */}
          {displayedResults.length > 0 && (
            <section className={styles.section}>
              <div className={styles.sectionTitle}>Results</div>
              <ResultsTable comparisons={displayedResults} />
            </section>
          )}

          {/* Load Existing */}
          <section className={styles.section}>
            <button className={styles.loadBtn} onClick={handleLoadExisting}>
              <RefreshCw size={13} />
              Load Saved Results
            </button>
          </section>
        </div>
      </div>
    </div>
  );
}
