'use client';
import React, { useEffect } from 'react';
import type { Artifact } from '@/lib/schemas/artifact';
import styles from './ArtifactPreviewModal.module.css';

export interface ArtifactPreviewModalProps {
  artifact: Artifact | null;
  onClose: () => void;
}

export const ArtifactPreviewModal: React.FC<ArtifactPreviewModalProps> = ({ artifact, onClose }) => {
  useEffect(() => {
    if (!artifact) return;
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [artifact, onClose]);

  if (!artifact) return null;

  return (
    <div className={styles.backdrop} onClick={onClose} role="dialog" aria-modal="true" aria-label={`Preview: ${artifact.name}`}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.title}>{artifact.name}</span>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close preview">×</button>
        </div>
        <div className={styles.body}>
          {['screenshot', 'image'].includes(artifact.type) && artifact.previewUrl && (
            <img
              src={artifact.previewUrl}
              alt={artifact.name}
              className={styles.previewImg}
            />
          )}
          {artifact.type === 'report' && (
            <iframe
              src={artifact.url}
              className={styles.reportFrame}
              title={artifact.name}
              sandbox="allow-scripts allow-same-origin"
            />
          )}
        </div>
      </div>
    </div>
  );
};
