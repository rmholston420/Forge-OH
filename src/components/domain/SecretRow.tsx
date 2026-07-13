'use client';
import React, { useState } from 'react';
import type { Secret } from '@/lib/schemas/secret';
import styles from './SecretRow.module.css';

const scopeLabels: Record<'global' | 'workspace' | 'run' | 'user' | 'deployment', string> = {
  global: 'Global',
  workspace: 'Workspace',
  run: 'Run',
  user: 'User',
  deployment: 'Deployment',
};

export interface SecretRowProps {
  secret: Secret;
  onDelete?: (id: string) => void;
  onRotate?: (id: string) => void;
}

export const SecretRow: React.FC<SecretRowProps> = ({ secret, onDelete, onRotate }) => {
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <tr className={styles.row}>
      <td className={styles.nameCell}>
        <code className={styles.name}>{secret.name}</code>
        {secret.description && (
          <span className={styles.desc}>{secret.description}</span>
        )}
      </td>
      <td>
        <span className={[styles.scopeBadge, styles[`scopeBadge--${scopeLabels[secret.scope]}`]].join(' ')}>
          {secret.scope}
        </span>
      </td>
      <td className={styles.maskedCell}>
        <code className={styles.masked}>••••••••••••</code>
      </td>
      <td className={styles.dateCell}>
        {secret.lastRotatedAt
          ? new Date(secret.lastRotatedAt).toLocaleDateString()
          : <span className={styles.never}>Never</span>}
      </td>
      <td className={styles.actionsCell}>
        <button
          className={styles.actionBtn}
          onClick={() => onRotate?.(secret.id)}
          aria-label={`Rotate ${secret.name}`}
        >
          Rotate
        </button>
        {confirmDelete ? (
          <>
            <button
              className={[styles.actionBtn, styles['actionBtn--danger']].join(' ')}
              onClick={() => { onDelete?.(secret.id); setConfirmDelete(false); }}
            >
              Confirm
            </button>
            <button className={styles.actionBtn} onClick={() => setConfirmDelete(false)}>
              Cancel
            </button>
          </>
        ) : (
          <button
            className={[styles.actionBtn, styles['actionBtn--danger']].join(' ')}
            onClick={() => setConfirmDelete(true)}
            aria-label={`Delete ${secret.name}`}
          >
            Delete
          </button>
        )}
      </td>
    </tr>
  );
};
