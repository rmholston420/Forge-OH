'use client';
import React from 'react';
import type { FileDiffSummary } from '@/lib/schemas/file-diff';
import styles from './FileList.module.css';

const STATUS_ICONS: Record<FileDiffSummary['status'], string> = {
  added: 'A',
  modified: 'M',
  deleted: 'D',
  renamed: 'R',
  untracked: '?',
};

const STATUS_CLASSES: Record<FileDiffSummary['status'], string> = {
  added: 'added',
  modified: 'modified',
  deleted: 'deleted',
  renamed: 'renamed',
  untracked: 'untracked',
};

export interface FileListProps {
  files: FileDiffSummary[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
}

export const FileList: React.FC<FileListProps> = ({ files, selectedPath, onSelect }) => {
  const totalAdd = files.reduce((s, f) => s + f.additions, 0);
  const totalDel = files.reduce((s, f) => s + f.deletions, 0);

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <span className={styles.count}>{files.length} file{files.length !== 1 ? 's' : ''} changed</span>
        <span className={styles.stats}>
          <span className={styles.adds}>+{totalAdd}</span>
          <span className={styles.dels}>-{totalDel}</span>
        </span>
      </div>
      <ul className={styles.list} role="list">
        {files.map((f) => (
          <li key={f.path}>
            <button
              className={[
                styles.item,
                selectedPath === f.path ? styles['item--active'] : '',
              ].filter(Boolean).join(' ')}
              onClick={() => onSelect(f.path)}
              aria-pressed={selectedPath === f.path}
            >
              <span className={[styles.badge, styles[`badge--${STATUS_CLASSES[f.status]}`]].join(' ')}>
                {STATUS_ICONS[f.status]}
              </span>
              <span className={styles.path}>{f.path}</span>
              <span className={styles.linestats}>
                {f.additions > 0 && <span className={styles.adds}>+{f.additions}</span>}
                {f.deletions > 0 && <span className={styles.dels}>-{f.deletions}</span>}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};
