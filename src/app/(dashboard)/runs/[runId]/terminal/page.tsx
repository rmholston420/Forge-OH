'use client';
import React from 'react';
import { useRunCommands } from '@/features/terminal/hooks';
import { TerminalEmulator } from '@/components/domain/TerminalEmulator';
import { Banner } from '@/components/core/Banner';
import { Skeleton } from '@/components/core/Skeleton';
import styles from './terminal.module.css';

const FEATURE_ENABLED = process.env.NEXT_PUBLIC_FEATURE_TERMINAL_ENABLED !== 'false';

export default function RunTerminalPage({ params }: { params: { runId: string } }) {
  const { runId } = params;
  const { data: commands = [], isLoading, error } = useRunCommands(runId);

  if (!FEATURE_ENABLED) {
    return <Banner variant="info">Terminal is feature-flagged. Set NEXT_PUBLIC_FEATURE_TERMINAL_ENABLED=true.</Banner>;
  }

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <span className={styles.heading}>Terminal</span>
        <span className={styles.cmdCount}>{commands.length} command{commands.length !== 1 ? 's' : ''}</span>
      </div>
      {error && (
        <Banner variant="error">
          Failed to load terminal history: {error instanceof Error ? error.message : 'Error'}
        </Banner>
      )}
      {isLoading ? (
        <Skeleton width="100%" height={480} borderRadius="8px" />
      ) : (
        <TerminalEmulator commands={commands} sessionKey={runId} />
      )}
    </div>
  );
}
