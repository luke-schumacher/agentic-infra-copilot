import { useState } from 'react';
import { X, RefreshCw, Database, Loader2 } from 'lucide-react';
import styles from './Sidebar.module.css';
import { AgentCardItem } from './AgentCard';
import { indexDocuments } from '../../api/client';
import { AGENTS } from '../../types';
import type { AgentHealthMap } from '../../hooks/useAgentHealth';

interface Props {
  open: boolean;
  onClose: () => void;
  agents: AgentHealthMap;
  onRefresh: () => void;
  refreshing: boolean;
}

export function Sidebar({ open, onClose, agents, onRefresh, refreshing }: Props) {
  const [indexing, setIndexing] = useState(false);
  const [indexResult, setIndexResult] = useState<string | null>(null);

  const handleIndex = async () => {
    setIndexing(true);
    setIndexResult(null);
    const results = await Promise.all(AGENTS.map((a) => indexDocuments(a.url)));
    const total = results.reduce((s, r) => s + (r.indexed_count ?? 0), 0);
    const errs = results.flatMap((r) => r.error ? [r.error] : []);
    setIndexResult(errs.length > 0 ? `Error: ${errs[0]}` : `Indexed ${total} documents`);
    setIndexing(false);
  };

  return (
    <>
      <div className={`${styles.overlay} ${open ? styles.open : ''}`} onClick={onClose} />
      <aside className={`${styles.sidebar} ${open ? styles.open : ''}`}>
        <div className={styles.top}>
          <span className={styles.title}>System Status</span>
          <button className={styles.closeBtn} onClick={onClose}><X size={16} /></button>
        </div>
        <div className={styles.cards}>
          {AGENTS.map((a) => (
            <AgentCardItem key={a.id} name={a.name} port={a.port} health={agents[a.id]} />
          ))}
        </div>
        <div className={styles.actions}>
          <button className={styles.btn} onClick={onRefresh} disabled={refreshing}>
            <RefreshCw size={14} className={refreshing ? styles.spinning : ''} />
            {refreshing ? 'Refreshing…' : 'Refresh Status'}
          </button>
          <button className={`${styles.btn} ${styles.accent}`} onClick={handleIndex} disabled={indexing}>
            {indexing ? <Loader2 size={14} className={styles.spinning} /> : <Database size={14} />}
            {indexing ? 'Indexing…' : 'Index Documents'}
          </button>
          {indexResult && (
            <span className={`${styles.indexResult} ${indexResult.startsWith('Error') ? styles.err : styles.ok}`}>
              {indexResult}
            </span>
          )}
        </div>
      </aside>
    </>
  );
}
