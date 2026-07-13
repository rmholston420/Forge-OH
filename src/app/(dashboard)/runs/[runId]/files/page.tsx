'use client';
import React from 'react';
import { useRunFiles, useFileDiff } from '@/features/file-diff/hooks';
import { useFileDiffStore } from '@/features/file-diff/store';
import { FileList } from '@/components/domain/FileList';
import { DiffViewer } from '@/components/domain/DiffViewer';
import { EmptyState } from '@/components/core/EmptyState';
import { Skeleton } from '@/components/core/Skeleton';
import { Banner } from '@/components/core/Banner';
import styles from './files.module.css';

const FEATURE_ENABLED = process.env.NEXT_PUBLIC_FEATURE_CODE_REVIEW_ENABLED !== 'false';

export default function RunFilesPage({ params }: { params: { runId: string } }) {
  const { runId } = params;
  const { selectedPath, setSelectedPath, diffMode, setDiffMode } = useFileDiffStore();
  const { data: files = [], isLoading: filesLoading, error: filesError } = useRunFiles(runId);
  const { data: diff, isLoading: diffLoading } = useFileDiff(runId, selectedPath);

  if (!FEATURE_ENABLED) {
    return <Banner variant="info">Code review is feature-flagged. Set NEXT_PUBLIC_FEATURE_CODE_REVIEW_ENABLED=true.</Banner>;
  }

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <span className={styles.heading}>Changed Files</span>
        <div className={styles.modeToggle} role="group" aria-label="Diff mode">
          <button
            className={[styles.modeBtn, diffMode === 'split' ? styles['modeBtn--active'] : ''].filter(Boolean).join(' ')}
            onClick={() => setDiffMode('split')}
            aria-pressed={diffMode === 'split'}
          >
            Split
          </button>
          <button
            className={[styles.modeBtn, diffMode === 'unified' ? styles['modeBtn--active'] : ''].filter(Boolean).join(' ')}
            onClick={() => setDiffMode('unified')}
            aria-pressed={diffMode === 'unified'}
          >
            Unified
          </button>
        </div>
      </div>

      {filesError && (
        <Banner variant="error">Failed to load files: {filesError instanceof Error ? filesError.message : 'Error'}</Banner>
      )}

      <div className={styles.layout}>
        <div className={styles.sidebar}>
          {filesLoading && (
            <div className={styles.skeletonList}>
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className={styles.skeletonFile}>
                  <Skeleton width={18} height={18} borderRadius="4px" />
                  <Skeleton width={`${50 + i * 8}%`} height={12} />
                </div>
              ))}
            </div>
          )}
          {!filesLoading && files.length === 0 && (
            <EmptyState title="No files changed" description="File changes will appear here as the agent works." icon="📂" />
          )}
          {files.length > 0 && (
            <FileList
              files={files}
              selectedPath={selectedPath}
              onSelect={setSelectedPath}
            />
          )}
        </div>

        <div className={styles.main}>
          {!selectedPath && (
            <EmptyState
              title="Select a file"
              description="Choose a file from the list to view its diff."
              icon="⇐"
            />
          )}
          {selectedPath && diffLoading && (
            <div className={styles.diffSkeleton}>
              <Skeleton width="100%" height={480} borderRadius="8px" />
            </div>
          )}
          {selectedPath && !diffLoading && diff && (
            <DiffViewer diff={diff} mode={diffMode} />
          )}
        </div>
      </div>
    </div>
  );
}
