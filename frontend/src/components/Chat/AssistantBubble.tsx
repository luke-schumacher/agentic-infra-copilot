import { AlertTriangle } from 'lucide-react';
import styles from './AssistantBubble.module.css';
import { RiskBadge } from './RiskBadge';
import { MetaBar } from './MetaBar';
import { DelegationBadge } from './DelegationBadge';
import { SourcesPanel } from './SourcesPanel';
import { SpecialistPanel } from './SpecialistPanel';
import { ReasoningChain } from './ReasoningChain';
import type { Message } from '../../types';

export function AssistantBubble({ message }: { message: Message }) {
  if (message.error) {
    return (
      <div className={styles.bubble}>
        <div className={`${styles.inner} ${styles.errorBubble}`}>
          <div style={{ fontSize: 12, color: 'var(--status-err)', marginBottom: 4, fontWeight: 600 }}>Error</div>
          <div style={{ fontSize: 13 }}>{message.error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.bubble}>
      <div className={styles.inner}>
        {message.isPartial && (
          <div className={styles.partialWarning}>
            <AlertTriangle size={13} />
            Partial response — some agents did not respond
          </div>
        )}

        {message.riskLevel && (
          <div className={styles.header}>
            <RiskBadge level={message.riskLevel} />
          </div>
        )}

        <div className={styles.content}>{message.content}</div>

        <MetaBar
          confidence={message.confidence}
          responseType={message.responseType}
          processingTimeMs={message.processingTimeMs}
        />

        {message.delegation && message.delegation.length > 0 && (
          <DelegationBadge chain={message.delegation} />
        )}

        {message.sources && message.sources.length > 0 && (
          <SourcesPanel sources={message.sources} />
        )}

        {message.specialistFindings?.map((f, i) => (
          <SpecialistPanel key={i} findings={f} index={i} />
        ))}

        {message.reasoning && message.reasoning.length > 0 && (
          <ReasoningChain rounds={message.reasoning} />
        )}
      </div>
    </div>
  );
}
