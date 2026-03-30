import { Menu, BarChart2, FlaskConical, Network, MessageSquare } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import styles from './Header.module.css';
import { AGENTS, toDisplayStatus } from '../../types';
import type { AgentHealthMap } from '../../hooks/useAgentHealth';

interface Props {
  onMenuClick: () => void;
  agents: AgentHealthMap;
  onEvalClick: () => void;
}

const SHORT: Record<string, string> = { gov: 'Gov', hw: 'HW', tel: 'Tel' };

const NAV_LINKS = [
  { to: '/research',      label: 'Research',     Icon: FlaskConical },
  { to: '/architecture',  label: 'Architecture',  Icon: Network },
  { to: '/results',       label: 'Results',       Icon: BarChart2 },
  { to: '/',              label: 'Chat',          Icon: MessageSquare, end: true },
];

export function Header({ onMenuClick, agents, onEvalClick }: Props) {
  return (
    <header className={styles.header}>
      <button className={styles.menuBtn} onClick={onMenuClick} aria-label="Toggle sidebar">
        <Menu size={18} />
      </button>
      <span className={styles.brand}>
        Agentic Infra <span className={styles.brandAccent}>Co-Pilot</span>
      </span>
      <nav className={styles.nav}>
        {NAV_LINKS.map(({ to, label, Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`
            }
          >
            <Icon size={13} />
            <span className={styles.navLabel}>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className={styles.pills}>
        {AGENTS.map((a) => {
          const cls = toDisplayStatus(agents[a.id]?.status);
          return (
            <span key={a.id} className={styles.pill}>
              <span className={`${styles.dot} ${styles[cls]}`} />
              {SHORT[a.id]}
            </span>
          );
        })}
      </div>
      <button className={styles.evalBtn} onClick={onEvalClick} aria-label="Open evaluation panel">
        <BarChart2 size={14} />
        Evaluation
      </button>
    </header>
  );
}
