import { useState } from 'react';
import type { QueryContext } from '../../types';

const SCANNER_MODELS = [
  'MAGNETOM Vida', 'MAGNETOM Prisma', 'MAGNETOM Avanto', 'MAGNETOM Skyra', 'MAGNETOM Altea',
];
const INSTITUTION_TYPES = ['Hospital', 'Outpatient Clinic', 'Research Institute'];
const CUSTOMER_ID_RE = /^mr\d{5,}$/i;

const inp = (err: boolean): React.CSSProperties => ({
  background: 'var(--bg-elevated)',
  border: `1px solid ${err ? 'var(--status-err)' : 'var(--border-subtle)'}`,
  borderRadius: 'var(--radius-sm)',
  color: 'var(--text-primary)',
  padding: '5px 8px',
  fontSize: 12,
  outline: 'none',
  width: '100%',
});

const sel: React.CSSProperties = {
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--radius-sm)',
  color: 'var(--text-primary)',
  padding: '5px 8px',
  fontSize: 12,
  outline: 'none',
  width: '100%',
};

const lbl: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: 'var(--text-muted)',
  display: 'block',
  marginBottom: 3,
};

export function ContextRow({ context, onChange }: { context: QueryContext; onChange: (c: QueryContext) => void }) {
  const [touched, setTouched] = useState(false);
  const invalid = touched && context.customer_id.length > 0 && !CUSTOMER_ID_RE.test(context.customer_id);
  const set = <K extends keyof QueryContext>(k: K, v: QueryContext[K]) => onChange({ ...context, [k]: v });

  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-end',
      gap: 8,
      padding: '8px 12px',
      background: 'var(--bg-surface)',
      borderTop: '1px solid var(--border-subtle)',
      flexWrap: 'wrap',
    }}>
      <div style={{ flex: '0 0 130px', minWidth: 100 }}>
        <label style={lbl}>Customer ID</label>
        <input
          style={inp(invalid)}
          value={context.customer_id}
          placeholder="mr176430"
          onChange={(e) => set('customer_id', e.target.value)}
          onBlur={() => setTouched(true)}
          title={invalid ? 'Format: mr followed by 5+ digits (e.g. mr176430)' : undefined}
        />
        {invalid && <span style={{ fontSize: 10, color: 'var(--status-err)' }}>Format: mr12345…</span>}
      </div>

      <div style={{ flex: '0 0 160px', minWidth: 120 }}>
        <label style={lbl}>Scanner Model</label>
        <select style={sel} value={context.scanner_model} onChange={(e) => set('scanner_model', e.target.value)}>
          <option value="">Select…</option>
          {SCANNER_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>

      <div style={{ flex: '0 0 140px', minWidth: 110 }}>
        <label style={lbl}>Institution</label>
        <select style={sel} value={context.institution_type} onChange={(e) => set('institution_type', e.target.value)}>
          <option value="">Select…</option>
          {INSTITUTION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <div style={{ flex: 1, minWidth: 100 }}>
        <label style={lbl}>Location</label>
        <input
          style={inp(false)}
          value={context.location}
          placeholder="Munich, DE"
          onChange={(e) => set('location', e.target.value)}
        />
      </div>

      <div style={{ flex: '0 0 auto' }}>
        <label style={lbl}>Query Type</label>
        <div style={{ display: 'flex', gap: 4 }}>
          {(['symptom', 'general'] as const).map((t) => (
            <button
              key={t}
              onClick={() => set('query_type', t)}
              style={{
                padding: '5px 10px',
                borderRadius: 'var(--radius-sm)',
                fontSize: 12,
                border: '1px solid',
                borderColor: context.query_type === t ? 'var(--accent)' : 'var(--border-subtle)',
                background: context.query_type === t ? 'var(--accent-dim)' : 'var(--bg-elevated)',
                color: context.query_type === t ? 'var(--accent)' : 'var(--text-muted)',
                fontWeight: context.query_type === t ? 600 : 400,
                transition: 'all 0.15s',
              }}
            >
              {t === 'symptom' ? 'Symptom' : 'Question'}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
