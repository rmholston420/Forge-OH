import React from 'react';
import { Button } from '@/components/core/Button';
import styles from './ApprovalBanner.module.css';

export interface ApprovalBannerProps {
  context?: string;
  onApprove: () => void;
  onReject: () => void;
  loading?: boolean;
}

export const ApprovalBanner: React.FC<ApprovalBannerProps> = ({ context, onApprove, onReject, loading }) => {
  return (
    <div className={styles.banner} role="alert" aria-live="assertive">
      <div className={styles.left}>
        <span className={styles.icon} aria-hidden="true">⏸</span>
        <div className={styles.text}>
          <span className={styles.title}>Agent is awaiting your approval</span>
          {context && <span className={styles.context}>{context}</span>}
        </div>
      </div>
      <div className={styles.actions}>
        <Button
          variant="destructive"
          size="sm"
          onClick={onReject}
          loading={loading}
          aria-label="Reject agent action"
        >
          Reject
        </Button>
        <Button
          variant="primary"
          size="sm"
          onClick={onApprove}
          loading={loading}
          aria-label="Approve agent action"
        >
          ✓ Approve
        </Button>
      </div>
    </div>
  );
};
