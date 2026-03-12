import { ExpandablePanel } from '../shared/ExpandablePanel';
import type { ReasoningRound } from '../../types';

export function ReasoningChain({ rounds }: { rounds: ReasoningRound[] }) {
  if (!rounds?.length) return null;
  return (
    <ExpandablePanel title={`Reasoning chain (${rounds.length} rounds)`}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
        <thead>
          <tr style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>
            <th style={{ textAlign: 'left', padding: '4px 8px' }}>Round</th>
            <th style={{ textAlign: 'left', padding: '4px 8px' }}>Agent</th>
            <th style={{ textAlign: 'left', padding: '4px 8px' }}>Type</th>
            <th style={{ textAlign: 'right', padding: '4px 8px' }}>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {rounds.map((r) => (
            <tr key={r.round_number} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
              <td style={{ padding: '5px 8px', color: 'var(--text-muted)' }}>{r.round_number}</td>
              <td style={{ padding: '5px 8px' }}>{r.agent}</td>
              <td style={{ padding: '5px 8px', color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>
                {r.response_type ?? '—'}
              </td>
              <td style={{ padding: '5px 8px', textAlign: 'right', color: 'var(--text-muted)' }}>
                {r.confidence !== undefined ? `${Math.round(r.confidence * 100)}%` : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ExpandablePanel>
  );
}
