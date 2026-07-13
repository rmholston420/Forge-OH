import React, { useEffect } from 'react';
import styles from './Drawer.module.css';

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  side?: 'right' | 'left';
  width?: number | string;
}

export const Drawer: React.FC<DrawerProps> = ({ open, onClose, title, children, side = 'right', width = 384 }) => {
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  return (
    <>
      {open && <div className={styles.backdrop} onClick={onClose} aria-hidden="true" />}
      <div
        className={[styles.drawer, styles[`drawer--${side}`], open ? styles['drawer--open'] : ''].join(' ')}
        style={{ width }}
        role="complementary"
        aria-label={title}
      >
        <div className={styles.header}>
          <span className={styles.title}>{title}</span>
          <button className={styles.close} onClick={onClose} aria-label="Close drawer">×</button>
        </div>
        <div className={styles.body}>{children}</div>
      </div>
    </>
  );
};
