'use client';
import React from 'react';
import { useSecrets, useDeleteSecret, useRotateSecret } from '@/features/secrets/hooks';
import { useSecretsStore } from '@/features/secrets/store';
import { SecretRow } from '@/components/domain/SecretRow';
import { SecretUpsertModal } from '@/components/domain/SecretUpsertModal';
import { EmptyState } from '@/components/core/EmptyState';
import { Banner } from '@/components/core/Banner';
import { Skeleton } from '@/components/core/Skeleton';
import type { SecretScope } from '@/lib/schemas/secret';
import styles from './secrets.module.css';

const FEATURE_ENABLED = process.env.NEXT_PUBLIC_FEATURE_SECRETS_ENABLED !== 'false';

export default function SecretsPage() {
  const { scopeFilter, setScopeFilter, composerOpen, openComposer, closeComposer, rotatingId, setRotatingId } = useSecretsStore();
  const { data: secrets = [], isLoading, error } = useSecrets();
  const deleteMutation = useDeleteSecret();
  const rotateMutation = useRotateSecret();

  const filtered = scopeFilter === 'all' ? secrets : secrets.filter((s) => s.scope === scopeFilter);

  if (!FEATURE_ENABLED) {
    return <Banner variant="info">Secrets vault is feature-flagged. Set NEXT_PUBLIC_FEATURE_SECRETS_ENABLED=true.</Banner>;
  }

  const handleRotate = async (id: string) => {
    const newValue = prompt('Enter new secret value:');
    if (!newValue) return;
    await rotateMutation.mutateAsync({ id, value: newValue });
  };

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <div className={styles.filters} role="group" aria-label="Filter by scope">
          {(['all', 'global', 'workspace', 'run'] as (SecretScope | 'all')[]).map((s) => (
            <button
              key={s}
              className={[styles.filterBtn, scopeFilter === s ? styles['filterBtn--active'] : ''].filter(Boolean).join(' ')}
              onClick={() => setScopeFilter(s)}
              aria-pressed={scopeFilter === s}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
        <button className={styles.newBtn} onClick={openComposer}>
          + Add Secret
        </button>
      </div>

      <div className={styles.notice}>
        🔒 Secret values are write-only and never displayed. Store them in your password manager.
      </div>

      {error && (
        <Banner variant="error">Failed to load secrets: {error instanceof Error ? error.message : 'Error'}</Banner>
      )}

      {isLoading ? (
        <Skeleton width="100%" height={240} borderRadius="12px" />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No secrets"
          description="Secrets are injected as environment variables into agent runs."
          icon="🔑"
          action={{ label: 'Add Secret', onClick: openComposer }}
        />
      ) : (
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Name</th>
                <th>Scope</th>
                <th>Value</th>
                <th>Last Rotated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((secret) => (
                <SecretRow
                  key={secret.id}
                  secret={secret}
                  onDelete={(id) => deleteMutation.mutate(id)}
                  onRotate={handleRotate}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <SecretUpsertModal open={composerOpen} onClose={closeComposer} />
    </div>
  );
}
