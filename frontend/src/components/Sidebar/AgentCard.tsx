import { toDisplayStatus } from '../../types';
import type { AgentHealthStatus } from '../../types';

const DOT_COLORS = { ok: 'var(--status-ok)', warn: 'var(--status-warn)', err: 'var(--status-err)', unknown: 'var(--text-muted)' } as const;
const DOT_LABELS = { ok: 'Healthy', warn: 'Degraded', err: 'Unhealthy', unknown: 'Unknown' } as const;

export function AgentCardItem({ name, port, health }: { name: string; port: number; health?: AgentHealthStatus }) {
  const cls = toDisplayStatus(health?.status);
  return (
    <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '10px 12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{name}</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)' }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: DOT_COLORS[cls], display: 'inline-block' }} />
          {DOT_LABELS[cls]}
        </span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', flexWrap: 'wrap', gap: '4px 12px' }}>
        <span>:{port}</span>
        {health?.document_count !== undefined && <span>{health.document_count} docs</span>}
        {health?.dspy_ready !== undefined && <span>DSPy {health.dspy_ready ? '✓' : '✗'}</span>}
        {health?.vector_store_ready !== undefined && <span>VStore {health.vector_store_ready ? '✓' : '✗'}</span>}
        {health?.uptime_seconds !== undefined && <span>Up {Math.floor(health.uptime_seconds / 60)}m</span>}
      </div>
    </div>
  );
}
