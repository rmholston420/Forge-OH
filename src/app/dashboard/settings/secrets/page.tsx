'use client';

import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { SecretRow } from '@/components/domain/secret-row';
import { EmptyState } from '@/components/core/empty-state';
import { Skeleton } from '@/components/core/skeleton';
import { Modal } from '@/components/core/modal';
import { useSecrets, useCreateSecret, useDeleteSecret } from '@/features/secrets/hooks';
import { useSecretsStore } from '@/features//secrets/store';
import { CreateSecretRequestSchema } from '@/features/secrets/schemas';
import type { CreateSecretRequest, SecretScope } from '@/features/secrets/schemas';

const SCOPE_FILTERS: Array<{ value: SecretScope | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'global', label: 'Global' },
  { value: 'workspace', label: 'Workspace' },
  { value: 'run', label: 'Run' },
];

export default function SecretsPage() {
  const { data: secrets, isLoading, error } = useSecrets();
  const {
    addModalOpen,
    confirmDeleteId,
    searchQuery,
    scopeFilter,
    openAddModal,
    closeAddModal,
    setConfirmDeleteId,
    setSearchQuery,
    setScopeFilter,
  } = useSecretsStore();

  const createMutation = useCreateSecret();
  const deleteMutation = useDeleteSecret();

  const filtered = (secrets ?? []).filter((s) => {
    const matchesScope = scopeFilter === 'all' || s.scope === scopeFilter;
    const matchesSearch = s.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesScope && matchesSearch;
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateSecretRequest>({
    resolver: zodResolver(CreateSecretRequestSchema),
    defaultValues: { scope: 'global', provider: 'env' },
  });

  function onSubmit(data: CreateSecretRequest) {
    createMutation.mutate(data, {
      onSuccess: () => {
        reset();
        closeAddModal();
      },
    });
  }

  return (
    <main className="secrets-page">
      <header className="page-header">
        <h1 className="page-title">Secrets</h1>
        <button className="btn btn-primary btn-sm" onClick={openAddModal}>
          + Add Secret
        </button>
      </header>

      {/* Filters */}
      <div className="secrets-page__filters">
        <input
          className="input input-search"
          type="search"
          placeholder="Search secrets…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          aria-label="Search secrets by name"
        />
        <div className="filter-pills" role="group" aria-label="Filter by scope">
          {SCOPE_FILTERS.map(({ value, label }) => (
            <button
              key={value}
              className={`filter-pill${scopeFilter === value ? ' filter-pill--active' : ''}`}
              onClick={() => setScopeFilter(value as SecretScope | 'all')}
              aria-pressed={scopeFilter === value}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="secrets-skeleton">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="skeleton-text" style={{ height: '40px', marginBottom: '8px' }} />
          ))}
        </div>
      ) : error ? (
        <EmptyState icon="⚠" title="Failed to load secrets" description="Check your BFF connection." />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon="🔑"
          title={searchQuery ? 'No secrets match your search' : 'No secrets yet'}
          description={!searchQuery ? 'Add a secret to make it available to your agents.' : undefined}
          action={
            !searchQuery ? (
              <button className="btn btn-primary" onClick={openAddModal}>
                Add Secret
              </button>
            ) : undefined
          }
        />
      ) : (
        <table className="secrets-table" aria-label="Secrets vault">
          <thead>
            <tr>
              <th>Name</th>
              <th>Value</th>
              <th>Scope</th>
              <th>Provider</th>
              <th>Used In</th>
              <th>Created / Rotated</th>
              <th><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s) => (
              <SecretRow
                key={s.id}
                secret={s}
                onRotate={(id) => setConfirmDeleteId(`rotate:${id}`)}
                onDelete={(id) => setConfirmDeleteId(id)}
              />
            ))}
          </tbody>
        </table>
      )}

      {/* Add Secret Modal */}
      {addModalOpen && (
        <Modal title="Add Secret" onClose={closeAddModal}>
          <form onSubmit={handleSubmit(onSubmit)} className="form">
            <div className="form-field">
              <label htmlFor="secret-name">Name</label>
              <input
                id="secret-name"
                className={`input${errors.name ? ' input--error' : ''}`}
                {...register('name')}
                autoComplete="off"
              />
              {errors.name && (
                <p className="form-field__error" role="alert">{errors.name.message}</p>
              )}
            </div>

            <div className="form-field">
              <label htmlFor="secret-scope">Scope</label>
              <select id="secret-scope" className="input" {...register('scope')}>
                <option value="global">Global</option>
                <option value="workspace">Workspace</option>
                <option value="run">Run</option>
              </select>
            </div>

            <div className="form-field">
              <label htmlFor="secret-provider">Provider</label>
              <select id="secret-provider" className="input" {...register('provider')}>
                <option value="env">Environment Variable</option>
                <option value="vault">Vault</option>
                <option value="k8s-secret">Kubernetes Secret</option>
                <option value="plaintext">Plaintext (dev only)</option>
              </select>
            </div>

            <div className="form-field">
              <label htmlFor="secret-value">Value</label>
              <input
                id="secret-value"
                className={`input${errors.value ? ' input--error' : ''}`}
                type="password"
                autoComplete="new-password"
                {...register('value')}
              />
              {errors.value && (
                <p className="form-field__error" role="alert">{errors.value.message}</p>
              )}
            </div>

            <div className="form__actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={isSubmitting || createMutation.isPending}
              >
                {isSubmitting || createMutation.isPending ? 'Saving…' : 'Add Secret'}
              </button>
              <button type="button" className="btn btn-secondary" onClick={closeAddModal}>
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}
    </main>
  );
}
