import { ExpandablePanel } from '../shared/ExpandablePanel';
import type { DocumentReference } from '../../types';

export function SourcesPanel({ sources }: { sources: DocumentReference[] }) {
  if (!sources?.length) return null;
  return (
    <ExpandablePanel title={`${sources.length} source${sources.length !== 1 ? 's' : ''}`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {sources.map((src, i) => (
          <div
            key={i}
            style={{
              borderBottom: i < sources.length - 1 ? '1px solid var(--border-subtle)' : 'none',
              paddingBottom: i < sources.length - 1 ? 10 : 0,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 500 }}>{src.source}</span>
              {src.relevance_score !== undefined && (
                <span style={{ fontSize: 11, color: 'var(--accent)' }}>
                  {Math.round(src.relevance_score * 100)}%
                </span>
              )}
            </div>
            {src.file_name && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>{src.file_name}</div>
            )}
            {src.content_snippet && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5, fontStyle: 'italic' }}>
                "{src.content_snippet}"
              </div>
            )}
          </div>
        ))}
      </div>
    </ExpandablePanel>
  );
}
