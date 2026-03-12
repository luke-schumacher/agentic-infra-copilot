const TYPE_COLORS: Record<string, string> = {
  ANSWER:   '#60A5FA',
  PARTIAL:  '#F5A623',
  CLARIFY:  '#A78BFA',
  REDIRECT: '#34D399',
  REFUSE:   '#F87171',
  CONSULT:  '#F5A623',
};

interface Props {
  confidence?: number;
  responseType?: string;
  processingTimeMs?: number;
}

export function MetaBar({ confidence, responseType, processingTimeMs }: Props) {
  if (!confidence && !responseType && !processingTimeMs) return null;
  const color = responseType ? (TYPE_COLORS[responseType] ?? 'var(--text-muted)') : 'var(--text-muted)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
      {responseType && (
        <span style={{ fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', color, background: `${color}18`, padding: '2px 6px', borderRadius: 3, border: `1px solid ${color}30` }}>
          {responseType}
        </span>
      )}
      {confidence !== undefined && (
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {Math.round(confidence * 100)}% confidence
        </span>
      )}
      {processingTimeMs !== undefined && (
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {processingTimeMs < 1000 ? `${processingTimeMs}ms` : `${(processingTimeMs / 1000).toFixed(1)}s`}
        </span>
      )}
    </div>
  );
}
