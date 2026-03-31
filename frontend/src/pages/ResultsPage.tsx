import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, TrendingUp, BarChart2, Award, Activity, GitCompare } from 'lucide-react';
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
  governance_only:  'Governance Only',
  hardware_only:    'Hardware Only',
  telemetry_only:   'Telemetry Only',
  single_all_data:  'Single + All Data',
  mas_full:         'MAS Full',
};
const MODE_SHORT: Record<string, string> = {
  governance_only: 'Gov',
  hardware_only:   'HW',
  telemetry_only:  'Tel',
  single_all_data: 'Single+All',
  mas_full:        'MAS',
};
const MODES = ['governance_only', 'hardware_only', 'telemetry_only', 'single_all_data', 'mas_full'];

const ABLATION_MODES_DESC = [
  {
    mode: 'governance_only',
    color: '#60A5FA',
    label: 'Governance Only',
    desc: 'Governance Agent called with only institutional/SLA context. No hardware or telemetry data. Measures: workload patterns, policy retrieval.',
    weakness: 'Cannot diagnose hardware faults or safety compliance gaps.',
  },
  {
    mode: 'hardware_only',
    color: '#F5A623',
    label: 'Hardware Only',
    desc: 'Hardware Agent called with only technical/diagnostic context. DICOM conformance, failure modes, operator manuals.',
    weakness: 'Missing operational context — SLA implications unknown, safety compliance unchecked.',
  },
  {
    mode: 'telemetry_only',
    color: '#4ADE80',
    label: 'Telemetry Only',
    desc: 'Telemetry Agent called with only safety/event context. Safety zones, SOP compliance, event log patterns.',
    weakness: 'Cannot correlate events with hardware specs or SLA contracts.',
  },
  {
    mode: 'single_all_data',
    color: '#A78BFA',
    label: 'Single + All Data',
    desc: 'One agent given combined context from all three domains. Tests whether data completeness alone (without specialisation) drives performance.',
    weakness: 'No domain-specialised reasoning. The key test: does MAS > this baseline?',
  },
  {
    mode: 'mas_full',
    color: '#FB923C',
    label: 'MAS Full',
    desc: 'All three agents collaborate via A2A AgentCards. Parallel specialist delegation, up to 4 reasoning rounds, Claude Sonnet synthesis.',
    weakness: 'Target mode. Emergence is demonstrated when MAS > best(single modes).',
  },
];

const JUDGE_METRICS = [
  { metric: 'Accuracy', weight: 0.35, desc: 'Factual correctness vs ground truth', color: '#F87171' },
  { metric: 'Relevance', weight: 0.20, desc: 'Query relevance and specificity', color: '#FB923C' },
  { metric: 'Completeness', weight: 0.20, desc: 'Coverage of all required aspects', color: '#60A5FA' },
  { metric: 'Cross-Domain', weight: 0.25, desc: 'Synthesis quality across governance / hardware / telemetry', color: '#4ADE80' },
];

// ─── Sub-components ────────────────────────────────────────────────────────

function ScoreBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
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

function StatCard({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: boolean }) {
  return (
    <div className={`${styles.statCard} ${accent ? styles.statCardAccent : ''}`}>
      <div className={styles.statValue}>{value}</div>
      <div className={styles.statLabel}>{label}</div>
      {sub && <div className={styles.statSub}>{sub}</div>}
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────

export function ResultsPage() {
  const [liveResults, setLiveResults] = useState<AblationComparison[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'modes' | 'live' | 'emergence' | 'judge' | 'runs'>('overview');

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

  useEffect(() => { loadLive(); }, [loadLive]);

  const source = liveResults.length > 0 ? liveResults : null;
  const emergenceCount = source
    ? source.filter((c) => c.emergence_demonstrated).length
    : EMERGENCE_CASES.length;
  const totalCases = source ? source.length : 12;
  const masResult   = MODE_RESULTS.find((m) => m.mode === 'mas_full')!;
  const masAvg      = source
    ? Math.round((source.reduce((s, c) => s + c.mas_accuracy, 0) / source.length) * 100)
    : Math.round(masResult.avg_overall * 100);
  const singleModes = MODE_RESULTS.filter((m) => m.mode !== 'mas_full');
  const bestSingleAvg = source
    ? Math.round((source.reduce((s, c) => s + c.best_single_agent_accuracy, 0) / source.length) * 100)
    : Math.round(Math.max(...singleModes.map((m) => m.avg_overall)) * 100);

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerTitle}>
          <BarChart2 size={20} />
          Evaluation Results
        </div>
        <div className={styles.headerMeta}>
          Ablation study · 5 modes × 12 test cases · LLM-as-judge scoring · emergence detection
        </div>
      </div>

      {/* Key stats */}
      <div className={styles.statRow}>
        <StatCard label="MAS Avg Overall" value={`${masAvg}%`} sub="Run 2 pilot (12 cases)" accent />
        <StatCard label="Best Single Agent" value={`${bestSingleAvg}%`} sub="Single+All baseline" />
        <StatCard label="Emergence Gain" value={`+${masAvg - bestSingleAvg}%`} sub="MAS over best single" />
        <StatCard label="Emergence Rate" value={`${emergenceCount}/${totalCases}`} sub="Cases where MAS wins" />
        <StatCard label="Cross-Domain Weight" value="25%" sub="in judge scoring" />
        <StatCard label="Pass Threshold" value="0.60" sub="overall score to pass" />
      </div>

      {/* Tabs */}
      <div className={styles.tabs}>
        {([
          ['overview',  'Mode Scores',     BarChart2],
          ['modes',     'Ablation Modes',  GitCompare],
          ['live',      'Live Results',    Activity],
          ['emergence', 'Emergence',       TrendingUp],
          ['judge',     'Judge Metrics',   Award],
          ['runs',      'Run History',     RefreshCw],
        ] as const).map(([id, label, Icon]) => (
          <button
            key={id}
            className={`${styles.tab} ${activeTab === id ? styles.tabActive : ''}`}
            onClick={() => setActiveTab(id)}
          >
            <Icon size={12} />
            {label}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW ───────────────────────────────────── */}
      {activeTab === 'overview' && (
        <div className={styles.tabContent}>
          <table className={styles.modeTable}>
            <thead>
              <tr>
                <th>Mode</th>
                <th>Overall</th>
                <th>Accuracy <span className={styles.weight}>(×0.35)</span></th>
                <th>Relevance <span className={styles.weight}>(×0.20)</span></th>
                <th>Completeness <span className={styles.weight}>(×0.20)</span></th>
                <th>Cross-Domain <span className={styles.weight}>(×0.25)</span></th>
                <th>Pass Rate</th>
              </tr>
            </thead>
            <tbody>
              {[...MODE_RESULTS].sort((a, b) => b.avg_overall - a.avg_overall).map((r) => (
                <tr key={r.mode} className={r.mode === 'mas_full' ? styles.masRow : ''}>
                  <td className={styles.modeCell}>
                    {r.mode === 'mas_full' && <Award size={12} className={styles.masIcon} />}
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
            <div className={styles.sectionTitle}><BarChart2 size={13} /> Performance by Difficulty</div>
            <div className={styles.diffGrid}>
              {(['simple', 'moderate', 'complex'] as const).map((d) => {
                const b = DIFFICULTY_BREAKDOWN[d];
                const gap = Math.round((b.mas_avg - b.single_avg) * 100);
                return (
                  <div key={d} className={styles.diffCard}>
                    <div className={styles.diffCardHeader}>
                      <DiffBadge difficulty={d} />
                      <span className={styles.diffCount}>{b.count} cases</span>
                    </div>
                    <div className={styles.diffBars}>
                      <div className={styles.diffBarRow}>
                        <span>MAS</span>
                        <ScoreBar value={b.mas_avg} />
                      </div>
                      <div className={styles.diffBarRow}>
                        <span>Single best</span>
                        <ScoreBar value={b.single_avg} />
                      </div>
                    </div>
                    <div className={styles.diffGap}>
                      Emergence gap: <strong style={{ color: 'var(--status-ok)' }}>+{gap}%</strong>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── ABLATION MODES ─────────────────────────────── */}
      {activeTab === 'modes' && (
        <div className={styles.tabContent}>
          <div className={styles.modesIntro}>
            The ablation study isolates contributions of each domain and the MAS coordination layer.
            The critical comparison is <strong>MAS Full vs Single+All</strong> — if MAS wins,
            it proves that <em>specialisation + synthesis</em> adds value beyond data completeness alone.
          </div>
          <div className={styles.modeCardList}>
            {ABLATION_MODES_DESC.map((m) => {
              const scores = MODE_RESULTS.find((r) => r.mode === m.mode);
              return (
                <div key={m.mode} className={styles.modeCard} style={{ '--mc-color': m.color } as React.CSSProperties}>
                  <div className={styles.modeCardHeader}>
                    <span className={styles.modeColorDot} style={{ background: m.color }} />
                    <span className={styles.modeCardLabel}>{m.label}</span>
                    {scores && (
                      <span className={styles.modeCardScore}>
                        {Math.round(scores.avg_overall * 100)}% overall
                      </span>
                    )}
                  </div>
                  <p className={styles.modeCardDesc}>{m.desc}</p>
                  <div className={styles.modeWeakness}>
                    <span className={styles.weaknessLabel}>Limitation:</span> {m.weakness}
                  </div>
                  {scores && (
                    <div className={styles.modeScoreRow}>
                      {[
                        ['Acc', scores.avg_accuracy],
                        ['Rel', scores.avg_relevance],
                        ['Comp', scores.avg_completeness],
                        ['Cross', scores.avg_cross_domain],
                      ].map(([label, val]) => (
                        <div key={String(label)} className={styles.miniScore}>
                          <span>{label}</span>
                          <strong style={{ color: (val as number) >= 0.7 ? 'var(--status-ok)' : (val as number) >= 0.5 ? 'var(--status-warn)' : 'var(--status-err)' }}>
                            {Math.round((val as number) * 100)}%
                          </strong>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── LIVE RESULTS ───────────────────────────────── */}
      {activeTab === 'live' && (
        <div className={styles.tabContent}>
          <div className={styles.liveControls}>
            <button className={styles.refreshBtn} onClick={loadLive} disabled={loading}>
              <RefreshCw size={13} className={loading ? styles.spinning : ''} />
              {loading ? 'Loading…' : 'Refresh from API'}
            </button>
            {error && <span className={styles.errorMsg}>{error}</span>}
            {!error && liveResults.length === 0 && !loading && (
              <span className={styles.noData}>No saved results — run the evaluation suite first.</span>
            )}
            {liveResults.length > 0 && (
              <span className={styles.liveCount}>{liveResults.length} cases loaded</span>
            )}
          </div>
          {liveResults.length > 0 && (
            <>
              <div className={styles.liveStats}>
                <span>MAS avg: <strong>{masAvg}%</strong></span>
                <span>Best single: <strong>{bestSingleAvg}%</strong></span>
                <span>Emergence: <strong>{emergenceCount}/{liveResults.length} cases</strong></span>
                <span>Pass rate (MAS): <strong>{Math.round(liveResults.filter((c) => c.mas_accuracy >= 0.6).length / liveResults.length * 100)}%</strong></span>
              </div>
              <table className={styles.liveTable}>
                <thead>
                  <tr>
                    <th>Test Case</th>
                    <th>Diff</th>
                    {MODES.map((m) => <th key={m}>{MODE_SHORT[m]}</th>)}
                    <th>Emergence</th>
                    <th>Margin</th>
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
                      </td>
                      <td className={styles.marginCell}>
                        <span className={c.emergence_margin > 0 ? styles.marginPos : styles.marginNeg}>
                          {c.emergence_margin >= 0 ? '+' : ''}{Math.round(c.emergence_margin * 100)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {/* ── EMERGENCE ──────────────────────────────────── */}
      {activeTab === 'emergence' && (
        <div className={styles.tabContent}>
          <div className={styles.emergenceDefinition}>
            <TrendingUp size={16} />
            <div>
              <strong>Emergence criterion (dual condition):</strong>
              <span> MAS accuracy &gt; best single-agent accuracy </span>
              <span className={styles.andBadge}>AND</span>
              <span> (cross_domain_refs &gt; 0 OR judge cross_domain score &gt; 0.5)</span>
            </div>
          </div>

          <div className={styles.emergenceStats}>
            <div className={styles.emergenceStat}>
              <span className={styles.eStatNum}>{EMERGENCE_CASES.length}/{12}</span>
              <span className={styles.eStatLabel}>cases demonstrate emergence</span>
            </div>
            <div className={styles.emergenceStat}>
              <span className={styles.eStatNum}>+{Math.round(EMERGENCE_CASES.reduce((s, c) => s + c.margin, 0) / EMERGENCE_CASES.length * 100)}%</span>
              <span className={styles.eStatLabel}>avg emergence margin</span>
            </div>
            <div className={styles.emergenceStat}>
              <span className={styles.eStatNum}>5/5</span>
              <span className={styles.eStatLabel}>complex cases emerge</span>
            </div>
          </div>

          <div className={styles.emergenceList}>
            {[...EMERGENCE_CASES].sort((a, b) => b.margin - a.margin).map((c) => (
              <div key={c.name} className={styles.emergenceCard}>
                <div className={styles.emergenceCardHeader}>
                  <span className={styles.emergenceName}>{c.name.replace(/_/g, ' ')}</span>
                  <DiffBadge difficulty={c.difficulty} />
                  <span className={styles.emergenceMarginBadge}>+{Math.round(c.margin * 100)}%</span>
                </div>
                <div className={styles.emergenceScores}>
                  <div className={styles.emergenceScoreItem}>
                    <span>MAS</span>
                    <strong className={styles.scoreMas}>{Math.round(c.mas_score * 100)}%</strong>
                  </div>
                  <div className={styles.emergenceArrow}>→</div>
                  <div className={styles.emergenceScoreItem}>
                    <span>Best single</span>
                    <strong className={styles.scoreSingle}>{Math.round(c.best_single_score * 100)}%</strong>
                  </div>
                </div>
                <div className={styles.emergenceSynergy}>
                  <span className={styles.synergyLabel}>Domain synergy:</span> {c.domain_synergy}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── JUDGE METRICS ──────────────────────────────── */}
      {activeTab === 'judge' && (
        <div className={styles.tabContent}>
          <div className={styles.judgeIntro}>
            <strong>LLM-as-Judge:</strong> Claude Sonnet 4.5 evaluates each response against manually
            authored ground truth. Four metrics weighted into an overall score. Pass threshold: 0.60.
            Falls back to keyword-based scoring if DSPy is unavailable.
          </div>

          <div className={styles.metricGrid}>
            {JUDGE_METRICS.map((m) => (
              <div key={m.metric} className={styles.metricCard} style={{ '--mc': m.color } as React.CSSProperties}>
                <div className={styles.metricHeader}>
                  <span className={styles.metricName}>{m.metric}</span>
                  <span className={styles.metricWeight} style={{ color: m.color }}>
                    {Math.round(m.weight * 100)}% weight
                  </span>
                </div>
                <p className={styles.metricDesc}>{m.desc}</p>
                <div className={styles.metricBar}>
                  <div className={styles.metricBarFill} style={{ width: `${m.weight * 100}%`, background: m.color }} />
                </div>
              </div>
            ))}
          </div>

          <div className={styles.judgeFormula}>
            <div className={styles.sectionTitle}><Award size={13} /> Overall Score Formula</div>
            <div className={styles.formulaBox}>
              <code>
                overall = accuracy×0.35 + relevance×0.20 + completeness×0.20 + cross_domain×0.25
              </code>
            </div>
          </div>

          <div className={styles.judgeFallback}>
            <div className={styles.sectionTitle}><Activity size={13} /> Fallback Evaluation (keyword-based)</div>
            <div className={styles.fallbackBox}>
              {[
                ['Accuracy', 'Count required keywords found in response / total keywords'],
                ['Relevance', 'min(1.0, response_length / 200) — penalises very short responses'],
                ['Completeness', 'Same as accuracy (keyword coverage proxy)'],
                ['Cross-domain', 'Count how many of governance / hardware / telemetry term sets appear'],
              ].map(([metric, method]) => (
                <div key={String(metric)} className={styles.fallbackRow}>
                  <span className={styles.fallbackMetric}>{metric}</span>
                  <span className={styles.fallbackMethod}>{method}</span>
                </div>
              ))}
            </div>
          </div>

          <div className={styles.judgeScoreTable}>
            <div className={styles.sectionTitle}><BarChart2 size={13} /> Score by Mode (Run 2 Pilot)</div>
            <table className={styles.scoreTable}>
              <thead>
                <tr>
                  <th>Mode</th>
                  <th>Accuracy</th>
                  <th>Relevance</th>
                  <th>Completeness</th>
                  <th>Cross-Domain</th>
                  <th>Overall</th>
                  <th>Pass Rate</th>
                </tr>
              </thead>
              <tbody>
                {[...MODE_RESULTS].sort((a, b) => b.avg_overall - a.avg_overall).map((r) => (
                  <tr key={r.mode} className={r.mode === 'mas_full' ? styles.masRow : ''}>
                    <td className={styles.modeCell}>
                      {r.mode === 'mas_full' && <Award size={12} className={styles.masIcon} />}
                      {r.label}
                    </td>
                    <td className={`${styles.scoreCell} ${r.avg_accuracy >= 0.7 ? styles.cellGood : r.avg_accuracy >= 0.5 ? styles.cellMid : styles.cellBad}`}>
                      {Math.round(r.avg_accuracy * 100)}%
                    </td>
                    <td className={`${styles.scoreCell} ${r.avg_relevance >= 0.7 ? styles.cellGood : r.avg_relevance >= 0.5 ? styles.cellMid : styles.cellBad}`}>
                      {Math.round(r.avg_relevance * 100)}%
                    </td>
                    <td className={`${styles.scoreCell} ${r.avg_completeness >= 0.7 ? styles.cellGood : r.avg_completeness >= 0.5 ? styles.cellMid : styles.cellBad}`}>
                      {Math.round(r.avg_completeness * 100)}%
                    </td>
                    <td className={`${styles.scoreCell} ${r.avg_cross_domain >= 0.7 ? styles.cellGood : r.avg_cross_domain >= 0.5 ? styles.cellMid : styles.cellBad}`}>
                      {Math.round(r.avg_cross_domain * 100)}%
                    </td>
                    <td className={`${styles.scoreCell} ${r.avg_overall >= 0.7 ? styles.cellGood : r.avg_overall >= 0.5 ? styles.cellMid : styles.cellBad}`}>
                      <strong>{Math.round(r.avg_overall * 100)}%</strong>
                    </td>
                    <td className={styles.passRate}>{Math.round(r.pass_rate * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── RUN HISTORY ────────────────────────────────── */}
      {activeTab === 'runs' && (
        <div className={styles.tabContent}>
          <div className={styles.runsList}>
            {RUN_SUMMARIES.map((r) => (
              <div key={r.run_id} className={styles.runCard}>
                <div className={styles.runHeader}>
                  <span className={styles.runLabel}>{r.label}</span>
                  <span className={styles.runDate}>{r.date}</span>
                  <span className={styles.runCases}>{r.cases} cases · 5 modes = {r.cases * 5} evaluations</span>
                </div>
                <div className={styles.runNotes}>{r.notes}</div>
                {r.mas_overall > 0 ? (
                  <div className={styles.runStatsRow}>
                    <div className={styles.runStat}>
                      <span>MAS Overall</span>
                      <strong className={styles.cellGood}>{Math.round(r.mas_overall * 100)}%</strong>
                    </div>
                    <div className={styles.runStat}>
                      <span>Best Single</span>
                      <strong>{Math.round(r.best_single_overall * 100)}%</strong>
                    </div>
                    <div className={styles.runStat}>
                      <span>Emergence Gain</span>
                      <strong className={styles.cellGood}>+{Math.round((r.mas_overall - r.best_single_overall) * 100)}%</strong>
                    </div>
                    <div className={styles.runStat}>
                      <span>Emergence Rate</span>
                      <strong>{Math.round(r.emergence_rate * 100)}%</strong>
                    </div>
                  </div>
                ) : (
                  <div className={styles.runPending}>
                    Pending — primary evaluation run not yet conducted. Will use expanded dataset with operator manuals + safety PDFs and Azure Sonnet 4.5 judge.
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
