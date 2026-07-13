import React from 'react';
import styles from './Topbar.module.css';

export interface TopbarProps {
  title?: string;
  actions?: React.ReactNode;
  breadcrumbs?: Array<{ label: string; href?: string }>;
  onCommandPaletteOpen?: () => void;
}

export const Topbar: React.FC<TopbarProps> = ({ title, actions, breadcrumbs, onCommandPaletteOpen }) => {
  return (
    <header className={styles.topbar} role="banner">
      <div className={styles.left}>
        {breadcrumbs?.map((crumb, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className={styles.separator} aria-hidden="true">/</span>}
            {crumb.href
              ? <a href={crumb.href} className={styles.crumb}>{crumb.label}</a>
              : <span className={styles.crumbCurrent}>{crumb.label}</span>
            }
          </React.Fragment>
        ))}
        {title && !breadcrumbs && <span className={styles.title}>{title}</span>}
      </div>

      <div className={styles.right}>
        {actions}
        <button
          className={styles.cmdBtn}
          onClick={onCommandPaletteOpen}
          aria-label="Open command palette (Cmd+K)"
          title="Cmd+K"
        >
          <span aria-hidden="true">⌘K</span>
        </button>
      </div>
    </header>
  );
};
