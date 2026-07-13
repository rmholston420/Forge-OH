'use client';
import React from 'react';
import type { Artifact } from '@/lib/schemas/artifact';
import styles from './ArtifactCard.module.css';

const TYPE_ICON: Record<Artifact['type'], string> = {
  patch: '📤',
  file: '📄',
  screenshot: '🖼️',
  report: '📈',
  download: '⬇️',
  image: '🖼️',
  video: '🎥',
  log: '📝',
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export interface ArtifactCardProps {
  artifact: Artifact;
  onPreview?: (id: string) => void;
}

export const ArtifactCard: React.FC<ArtifactCardProps> = ({ artifact, onPreview }) => {
  const canPreview = ['screenshot', 'image', 'report'].includes(artifact.type);

  return (
    <article className={styles.card}>
      {artifact.previewUrl && ['screenshot', 'image'].includes(artifact.type) ? (
        <button
          className={styles.previewThumb}
          onClick={() => onPreview?.(artifact.id)}
          aria-label={`Preview ${artifact.name}`}
        >
          <img
            src={artifact.previewUrl!}
            alt={artifact.name}
            width={280}
            height={160}
            loading="lazy"
            className={styles.thumbImg}
          />
          <span className={styles.previewOverlay} aria-hidden="true">🔍</span>
        </button>
      ) : (
        <div className={styles.iconThumb} aria-hidden="true">
          {TYPE_ICON[artifact.type]}
        </div>
      )}
      <div className={styles.meta}>
        <span className={styles.name}>{artifact.name}</span>
        <span className={styles.detail}>{artifact.mimeType} · {formatSize(artifact.sizeBytes)}</span>
      </div>
      <div className={styles.actions}>
        {canPreview && (
          <button
            className={styles.actionBtn}
            onClick={() => onPreview?.(artifact.id)}
            aria-label={`Preview ${artifact.name}`}
          >
            Preview
          </button>
        )}
        <a
          href={artifact.url}
          download={artifact.name}
          className={styles.actionBtn}
          aria-label={`Download ${artifact.name}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Download
        </a>
      </div>
    </article>
  );
};
