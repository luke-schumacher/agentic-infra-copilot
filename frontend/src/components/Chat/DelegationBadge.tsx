export function DelegationBadge({ chain }: { chain: string[] }) {
  if (!chain?.length) return null;
  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      fontSize: 11,
      color: 'var(--text-muted)',
      marginTop: 6,
      background: 'var(--bg-elevated)',
      border: '1px solid var(--border-subtle)',
      borderRadius: 4,
      padding: '3px 8px',
    }}>
      <span style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontSize: 10 }}>→</span>
      {chain.join(' → ')}
    </div>
  );
}
