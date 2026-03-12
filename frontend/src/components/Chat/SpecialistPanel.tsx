import { ExpandablePanel } from '../shared/ExpandablePanel';
import { extractContent } from '../../types';
import type { SpecialistFindings } from '../../types';

export function SpecialistPanel({ findings, index }: { findings: SpecialistFindings; index: number }) {
  const content = extractContent(findings.response_card);
  const riskLevel = findings.response_card?.payload?.risk_level;

  return (
    <ExpandablePanel title={`${findings.agent ?? `Specialist ${index + 1}`} Findings`}>
      <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.6 }}>
        {content && <p style={{ marginBottom: 6 }}>{content}</p>}
        {riskLevel && (
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Risk: <span style={{ color: 'var(--status-warn)', fontWeight: 600 }}>{String(riskLevel)}</span>
          </div>
        )}
        {findings.processing_time_ms !== undefined && (
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            {findings.processing_time_ms < 1000
              ? `${findings.processing_time_ms}ms`
              : `${(findings.processing_time_ms / 1000).toFixed(1)}s`}
          </div>
        )}
      </div>
    </ExpandablePanel>
  );
}
