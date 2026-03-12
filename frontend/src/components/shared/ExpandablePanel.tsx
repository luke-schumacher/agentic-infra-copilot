import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import styles from './ExpandablePanel.module.css';

interface Props {
  title: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export function ExpandablePanel({ title, defaultOpen = false, children }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={styles.panel}>
      <button className={styles.header} onClick={() => setOpen(!open)}>
        <span className={styles.title}>{title}</span>
        <ChevronDown size={14} className={`${styles.icon} ${open ? styles.open : ''}`} />
      </button>
      <div className={`${styles.content} ${open ? styles.open : ''}`}>
        <div className={styles.inner}>{children}</div>
      </div>
    </div>
  );
}
