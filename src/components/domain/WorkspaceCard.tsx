'use client';
import React from 'react';
import type { Workspace } from '@/lib/schemas/workspace';
import styles from './WorkspaceCard.module.css';

const TYPE_LABEL: Record<Workspace['type'], string> = {
  local: 'Local',
  docker: 'Docker',
  remote_api: 'Remote API',
};

const TYPE_ICON: Record<Workspace['type'], string> = {
  local: '🖥️',
  docker: '🐳',
  remote_api: '🌐',
};

const STATUS_CLASS: Record<Workspace['status'], string> = {
  active: 'active',
  inactive: 'inactive',
  error: 'error',
  provisioning: 'provisioning',
};

export interface WorkspaceCardProps {
  workspace: Workspace;
  onEdit?: (id: string) => void;
  onDelete?: (id: string) => void;
  onTest?: (id: string) => void;
}

export const WorkspaceCard: React.FC<WorkspaceCardProps> = ({
  workspace, onEdit, onDelete, onTest,
}) => (
  <article className={styles.card}>
    <div className={styles.header}>
      <span className={styles.typeIcon} aria-hidden="true">{TYPE_ICON[workspace.type]}</span>
      <div className={styles.titleRow}>
        <span className={styles.name}>{workspace.name}</span>
        <span className={[styles.statusDot, styles[`statusDot--${STATUS_CLASS[workspace.status]}`]].join(' ')}
          title={workspace.status} aria-label={`Status: ${workspace.status}`} />
      </div>
      <span className={styles.typeBadge}>{TYPE_LABEL[workspace.type]}</span>
    </div>
    {workspace.description && (
      <p className={styles.description}>{workspace.description}</p>
    )}
    <dl className={styles.meta}>
      {workspace.baseDir && (
        <><dt>Dir</dt><dd className={styles.code}>{workspace.baseDir}</dd></>
      )}
      {workspace.dockerImage && (
        <><dt>Image</dt><dd className={styles.code}>{workspace.dockerImage}</dd></>
      )}
      {workspace.remoteUrl && (
        <><dt>URL</dt><dd className={styles.code}>{workspace.remoteUrl}</dd></>
      )}
      <dt>Runs</dt><dd>{workspace.activeRunCount} active</dd>
    </dl>
    <div className={styles.actions}>
      <button className={styles.btn} onClick={() => onTest?.(workspace.id)} aria-label="Test connection">
        Test
      </button>
      <button className={styles.btn} onClick={() => onEdit?.(workspace.id)} aria-label="Edit workspace">
        Edit
      </button>
      <button
        className={[styles.btn, styles['btn--danger']].join(' ')}
        onClick={() => onDelete?.(workspace.id)}
        aria-label="Delete workspace"
        disabled={workspace.activeRunCount > 0}
      >
        Delete
      </button>
    </div>
  </article>
);
