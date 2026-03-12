export function UserBubble({ content }: { content: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '6px 0' }}>
      <div style={{
        maxWidth: '70%',
        background: 'var(--accent-dim)',
        border: '1px solid rgba(245,166,35,0.2)',
        borderRadius: 'var(--radius-lg)',
        padding: '10px 14px',
        fontSize: 14,
        color: 'var(--text-primary)',
        lineHeight: 1.6,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>
        {content}
      </div>
    </div>
  );
}
