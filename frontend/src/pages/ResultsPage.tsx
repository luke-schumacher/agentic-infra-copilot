import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, TrendingUp, BarChart2, Award } from 'lucide-react';
import styles from './ResultsPage.module.css';
import { getEvalResults } from '../api/evaluation';
import type { AblationComparison } from '../types';
import {
  MODE_RESULTS,
  RUN_SUMMARIES,
  EMERGENCE_CASES,
  DIFFICULTY_BREAKDOWN,
} from '../data/thesisResults';

const MODE_LABELS: Record<string, string> = {
  governance_only: 'Gov',
  hardware_only: 'HW',
  telemetry_only: 'Tel',
  single_all_data: 'Single+All',
  mas_full: 'MAS',
};
const MODES = ['governance_only', 'hardware_only', 'telemetry_only', 'single_all_data', 'mas_full'];

function ScoreBar({ value, max = 1 }: { value: number; max?: number }) {
  const pct = Math.round((value / max) * 100);
  const cls = pct >= 70 ? styles.barGood : pct >= 50 ? styles.barMid : styles.barBad;
  return (
    <div className={styles.scoreBarWrap}>
      <div className={`${styles.scoreBar} ${cls}`} style={{ width: `${pct}%` }} />
      <span className={styles.scoreLabel}>{pct}%</span>
    </div>
  );
}

function DiffBadge({ difficulty }: { difficulty: string }) {
  return <span className={styles.diffBadge} data-difficulty={difficulty}>{difficulty}</span>;
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className={styles.statCard}>
      <div className={styles.statValue}>{value}</div>
      <div className={styles.statLabel}>{label}</div>
      {sub && <div className={styles.statSub}>{sub}</div>}
    </div>
  );
}

export function ResultsPage() {
  const [liveResults, setLiveResults] = useState<AblationComparison[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'live' | 'emergence' | 'runs'>('overview');

  const loadLive = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getEvalResults();
      setLiveResults(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLive();
  }, [loadLive]);

  // Compute emergence stats from live data if available, else static
  const source = liveResults.length > 0 ? liveResults : null;
  const emergenceCount = source
    ? source.filter((c) => c.emergence_demonstrated).length
    : EMERGENCE_CASES.length;
  const totalCases = source ? source.length : 12;
  const masAvg = source
    ? Math.round((source.reduce((s, c) => s + c.mas_accuracy, 0) / source.length) * 100)
    : Math.round(MODE_RESULTS.find((m) => m.mode === 'mas_full')!.avg_overall * 100);
  const bestSingleAvg = source
    ? Math.round((source.reduce((s, c) => s + c.best_single_agent_accuracy, 0) / source.length) * 100)
    : Math.round(Math.max(...MODE_RESULTS.filter((m) => m.mode !== 'mas_full').map((m) => m.avg_overall)) * 100);

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerTitle}>
          <BarChart2 size={20} />
          Evaluation Results
        </div>
        <div className={styles.headerMeta}>
          Ablation study: 5 modes × 12 test cases — measuring MAS emergence
        </div>
      </div>

      {/* Summary stats */}
      <div className={styles.statRow}>
        <StatCard label="MAS Avg Overall" value={`${masAvg}%`} sub="vs single-agent baseline" />
        <StatCard label="Best Single Agent" value={`${bestSingleAvg}%`} sub="hardware_only / single_all_data" />
        <StatCard
          label="Emergence Rate"
          value={`${emergenceCount}/${totalCases}`}
          sub="MAS > best single agent"
        />
        <StatCard
          label="Emergence Gain"
          value={`+${masAvg - bestSingleAvg}%`}
          sub="avg margin over best single"
        />
      </div>

      {/* Tab nav */}
      <div className={styles.tabs}>
        {(['overview', 'live', 'emergence', 'runs'] as const).map((t) => (
          <button
            key={t}
            className={`${styles.tab} ${activeTab === t ? styles.tabActive : ''}`}
            onClick={() => setActiveTab(t)}
          >
            {t === 'overview' ? 'Mode Overview' : t === 'live' ? 'Live Results' : t === 'emergence' ? 'Emergence Cases' : 'Run History'}
          </button>
        ))}
      </div>

      {/* Overview tab */}
      {activeTab === 'overview' && (
        <div className={styles.tabContent}>
          <table className={styles.modeTable}>
            <thead>
              <tr>
                <th>Mode</th>
                <th>Overall</th>
                <th>Accuracy</th>
                <th>Relevance</th>
                <th>Completeness</th>
                <th>Cross-Domain</th>
                <th>Pass Rate</th>
              </tr>
            </thead>
            <tbody>
              {MODE_RESULTS.sort((a, b) => b.avg_overall - a.avg_overall).map((r) => (
                <tr key={r.mode} className={r.mode === 'mas_full' ? styles.masRow : ''}>
                  <td className={styles.modeCell}>
                    {r.mode === 'mas_full' && <Award size={13} className={styles.masIcon} />}
                    {r.label}
                  </td>
                  <td><ScoreBar value={r.avg_overall} /></td>
                  <td><ScoreBar value={r.avg_accuracy} /></td>
                  <td><ScoreBar value={r.avg_relevance} /></td>
                  <td><ScoreBar value={r.avg_completeness} /></td>
                  <td><ScoreBar value={r.avg_cross_domain} /></td>
                  <td className={styles.passRate}>{Math.round(r.pass_rate * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className={styles.diffSection}>
            <div className={styles.sectionTitle}>By Difficulty</div>
            <div className={styles.diffGrid}>
              {(['simple', 'moderate', 'complex'] as const).map((d) => {
                const b = DIFFICULTY_BREAKDOWN[d];
                return (
                  <div key={d} className={styles.diffCard}>
                    <DiffBadge difficulty={d} />
                    <div className={styles.diffStat}>
                      <span>MAS avg</span>
                      <strong>{Math.round(b.mas_avg * 100)}%</strong>
                    </div>
                    <div className={styles.diffStat}>
                      <span>Single avg</span>
                      <strong>{Math.round(b.single_avg * 100)}%</strong>
                    </div>
                    <div className={styles.diffStat}>
                      <span>Cases</span>
                      <strong>{b.count}</strong>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Live results tab */}
      {activeTab === 'live' && (
        <div className={styles.tabContent}>
          <div className={styles.liveControls}>
            <button className={styles.refreshBtn} onClick={loadLive} disabled={loading}>
              <RefreshCw size={13} className={loading ? styles.spinning : ''} />
              {loading ? 'Loading…' : 'Refresh'}
            </button>
            {error && <span className={styles.errorMsg}>{error}</span>}
            {!error && liveResults.length === 0 && !loading && (
              <span className={styles.noData}>No saved results found. Run the evaluation suite first.</span>
            )}
          </div>
          {liveResults.length > 0 && (
            <table className={styles.liveTable}>
              <thead>
                <tr>
                  <th>Test Case</th>
                  <th>Difficulty</th>
                  {MODES.map((m) => <th key={m}>{MODE_LABELS[m]}</th>)}
                  <th>Emergence</th>
                </tr>
              </thead>
              <tbody>
                {liveResults.map((c) => (
                  <tr key={c.test_case_name}>
                    <td className={styles.caseCell}>{c.test_case_name.replace(/_/g, ' ')}</td>
                    <td><DiffBadge difficulty={c.test_case_difficulty} /></td>
                    {MODES.map((m) => {
                      const v = c.results[m]?.accuracy_score;
                      if (v === undefined) return <td key={m} className={styles.naCell}>—</td>;
                      const pct = Math.round(v * 100);
                      const cls = pct >= 70 ? styles.cellGood : pct >= 40 ? styles.cellMid : styles.cellBad;
                      return <td key={m} className={`${styles.accuracyCell} ${cls}`}>{pct}%</td>;
                    })}
                    <td className={c.emergence_demonstrated ? styles.emergenceYes : styles.emergenceNo}>
                      {c.emergence_demonstrated ? 'YES' : 'no'}
                      <span className={styles.margin}>
                        {c.emergence_margin >= 0 ? '+' : ''}{Math.round(c.emergence_margin * 100)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Emergence cases tab */}
      {activeTab === 'emergence' && (
        <div className={styles.tabContent}>
          <div className={styles.emergenceIntro}>
            <TrendingUp size={16} />
            <span>
              Emergence is demonstrated when MAS accuracy exceeds the best single-agent baseline.
              These {EMERGENCE_CASES.length} cases show clear cross-domain synergy.
            </span>
          </div>
          <div className={styles.emergenceList}>
            {EMERGENCE_CASES.sort((a, b) => b.margin - a.margin).map((c) => (
              <div key={c.name} className={styles.emergenceCard}>
                <div className={styles.emergenceCardHeader}>
                  <span className={styles.emergenceName}>{c.name.replace(/_/g, ' ')}</span>
                  <DiffBadge difficulty={c.difficulty} />
                  <span className={styles.emergenceMargin}>+{Math.round(c.margin * 100)}%</span>
                </div>
                <div className={styles.emergenceScores}>
                  <span>MAS: <strong>{Math.round(c.mas_score * 100)}%</strong></span>
                  <span>Best single: <strong>{Math.round(c.best_single_score * 100)}%</strong></span>
                </div>
                <div className={styles.emergenceSynergy}>{c.domain_synergy}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Run history tab */}
      {activeTab === 'runs' && (
        <div className={styles.tabContent}>
          <div className={styles.runsList}>
            {RUN_SUMMARIES.map((r) => (
              <div key={r.run_id} className={styles.runCard}>
                <div className={styles.runHeader}>
                  <span className={styles.runLabel}>{r.label}</span>
                  <span className={styles.runDate}>{r.date}</span>
                  <span className={styles.runCases}>{r.cases} cases</span>
                </div>
                <div className={styles.runNotes}>{r.notes}</div>
                {r.mas_overall > 0 && (
                  <div className={styles.runStats}>
                    <span>MAS: <strong>{Math.round(r.mas_overall * 100)}%</strong></span>
                    <span>Best single: <strong>{Math.round(r.best_single_overall * 100)}%</strong></span>
                    <span>Emergence: <strong>{Math.round(r.emergence_rate * 100)}%</strong></span>
                  </div>
                )}
                {r.mas_overall === 0 && (
                  <div className={styles.runPending}>Pending — primary evaluation run not yet conducted</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
