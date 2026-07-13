import React from 'react';
import styles from './Panel.module.css';

export interface PanelProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
  noPadding?: boolean;
}

export const Panel: React.FC<PanelProps> = ({ title, children, className = '', noPadding = false }) => {
  return (
    <div className={[styles.panel, className].join(' ')}>
      {title && <div className={styles.header}><span className={styles.title}>{title}</span></div>}
      <div className={noPadding ? '' : styles.body}>{children}</div>
    </div>
  );
};
