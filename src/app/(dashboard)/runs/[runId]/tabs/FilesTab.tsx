'use client';
import React, { useState } from 'react';
import {
  useRunFiles,
  useFileDiff,
  useGitChanges,
  useGitDiff,
} from '@/features/file-diff/hooks';
import { useFileDiffStore } from '@/features/file-diff/store';
import { useRunDetail } from '@/features/run-detail/hooks';
import { FileList } from '@/components/domain/FileList';
import { DiffViewer } from '@/components/domain/DiffViewer';
import { EmptyState } from '@/components/core/EmptyState';
import { Skeleton } from '@/components/core/Skeleton';
import { Banner } from '@/components/core/Banner';
import styles from '../files/files.module.css';

const FEATURE_ENABLED = process.env.NEXT_PUBLIC_FEATURE_CODE_REVIEW_ENABLED !== 'false';
const REAL_GIT_DIFF_ENABLED =
  process.env.NEXT_PUBLIC_FEATURE_REAL_GIT_DIFF_ENABLED !== 'false';

export function FilesTab({ runId }: { runId: string }) {
  const { selectedPath, setSelectedPath, diffMode, setDiffMode } = useFileDiffStore();
  const { data: run } = useRunDetail(runId);
  const workspacePath =
    run?.workspaceType === 'local' && run.workspaceId?.startsWith('/')
      ? run.workspaceId
      : null;
  const [source, setSource] = useState<'events' | 'git'>('events');
  const useGit = REAL_GIT_DIFF_ENABLED && source === 'git' && !!workspacePath;

  const reconstructedFiles = useRunFiles(runId);
  const reconstructedDiff = useFileDiff(runId, useGit ? null : selectedPath);
  const gitChanges = useGitChanges(runId, useGit ? workspacePath : null);
  const gitDiffQuery = useGitDiff(
    runId,
    useGit ? selectedPath : null,
    useGit ? workspacePath : null,
    gitChanges.data?.find((f) => f.path === selectedPath)?.status,
  );

  const files = useGit ? gitChanges.data ?? [] : reconstructedFiles.data ?? [];
  const filesLoading = useGit ? gitChanges.isLoading : reconstructedFiles.isLoading;
  const filesError = useGit ? gitChanges.error : reconstructedFiles.error;
  const diff = useGit ? gitDiffQuery.data : reconstructedDiff.data;
  const diffLoading = useGit ? gitDiffQuery.isLoading : reconstructedDiff.isLoading;

  if (!FEATURE_ENABLED) {
    return (
      <Banner variant="info">
        Code review is feature-flagged. Set NEXT_PUBLIC_FEATURE_CODE_REVIEW_ENABLED=true.
      </Banner>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <span className={styles.heading}>Changed Files</span>
        {REAL_GIT_DIFF_ENABLED && workspacePath && (
          <div
            className={styles.modeToggle}
            role="group"
            aria-label="Diff source"
            data-testid="diff-source-toggle"
          >
            <button
              className={[
                styles.modeBtn,
                source === 'events' ? styles['modeBtn--active'] : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => {
                setSource('events');
                setSelectedPath(null);
              }}
              aria-pressed={source === 'events'}
            >
              Reconstructed
            </button>
            <button
              className={[
                styles.modeBtn,
                source === 'git' ? styles['modeBtn--active'] : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => {
                setSource('git');
                setSelectedPath(null);
              }}
              aria-pressed={source === 'git'}
              data-testid="diff-source-git"
            >
              Real git diff
            </button>
          </div>
        )}
        <div className={styles.modeToggle} role="group" aria-label="Diff mode">
          <button
            className={[styles.modeBtn, diffMode === 'split' ? styles['modeBtn--active'] : '']
              .filter(Boolean)
              .join(' ')}
            onClick={() => setDiffMode('split')}
            aria-pressed={diffMode === 'split'}
          >
            Split
          </button>
          <button
            className={[styles.modeBtn, diffMode === 'unified' ? styles['modeBtn--active'] : '']
              .filter(Boolean)
              .join(' ')}
            onClick={() => setDiffMode('unified')}
            aria-pressed={diffMode === 'unified'}
          >
            Unified
          </button>
        </div>
      </div>

      {filesError && (
        <Banner variant="error">
          Failed to load files: {filesError instanceof Error ? filesError.message : 'Error'}
        </Banner>
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
            <EmptyState
              title="No files changed"
              description="File changes will appear here as the agent works."
              icon="📂"
            />
          )}
          {files.length > 0 && (
            <FileList files={files} selectedPath={selectedPath} onSelect={setSelectedPath} />
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
          {selectedPath && !diffLoading && diff && <DiffViewer diff={diff} mode={diffMode} />}
        </div>
      </div>
    </div>
  );
}

export default FilesTab;
