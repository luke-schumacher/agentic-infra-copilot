const RISK: Record<string, { bg: string; color: string }> = {
  CRITICAL: { bg: 'rgba(248,113,113,0.15)', color: '#F87171' },
  HIGH:     { bg: 'rgba(251,146,60,0.15)',  color: '#FB923C' },
  MEDIUM:   { bg: 'rgba(245,166,35,0.15)',  color: '#F5A623' },
  LOW:      { bg: 'rgba(74,222,128,0.15)',  color: '#4ADE80' },
};

export function RiskBadge({ level }: { level: string }) {
  const c = RISK[level.toUpperCase()] ?? { bg: 'var(--bg-elevated)', color: 'var(--text-muted)' };
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 4,
      fontSize: 11,
      fontWeight: 700,
      fontFamily: 'var(--font-mono)',
      letterSpacing: '0.05em',
      background: c.bg,
      color: c.color,
      border: `1px solid ${c.color}40`,
    }}>
      {level.toUpperCase()}
    </span>
  );
}
