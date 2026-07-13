import React from 'react';
import styles from './Banner.module.css';

export type BannerVariant = 'info' | 'success' | 'warning' | 'error';

export interface BannerProps {
  variant?: BannerVariant;
  title?: string;
  children: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
}

export const Banner: React.FC<BannerProps> = ({ variant = 'info', title, children, onDismiss, className = '' }) => {
  return (
    <div className={[styles.banner, styles[`banner--${variant}`], className].join(' ')} role="alert">
      <div className={styles.content}>
        {title && <span className={styles.title}>{title}</span>}
        <span className={styles.body}>{children}</span>
      </div>
      {onDismiss && (
        <button className={styles.dismiss} onClick={onDismiss} aria-label="Dismiss banner">
          ×
        </button>
      )}
    </div>
  );
};
