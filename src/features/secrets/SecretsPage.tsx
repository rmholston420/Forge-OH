'use client';
import { useSecrets } from './hooks';
import { useSecretsStore } from './store';
import { SecretRow } from './SecretRow';
import { CanDo } from '@/components/auth/CanDo';
import { Permission } from '@/lib/rbac/permissions';
import type { SecretScope } from './schemas';

const SCOPE_FILTERS: { label: string; value: SecretScope | 'all' }[] = [
  { label: 'All',       value: 'all'       },
  { label: 'Global',    value: 'global'    },
  { label: 'Workspace', value: 'workspace' },
  { label: 'Run',       value: 'run'       },
];

export default function SecretsPage() {
  const { data: secrets = [], isLoading } = useSecrets();
  const { scopeFilter, setScopeFilter, openAddDrawer, confirmDeleteId, setConfirmDeleteId } =
    useSecretsStore();

  const filtered = scopeFilter === 'all'
    ? secrets
    : secrets.filter(s => s.scope === scopeFilter);

  return (
    <div className="secrets-page">
      <div className="page-header">
        <div>
          <h1>Secrets Vault</h1>
          <p className="page-subtitle">
            {secrets.length} secret{secrets.length !== 1 ? 's' : ''} stored
          </p>
        </div>
        <CanDo permission={Permission.SECRETS_WRITE}>
          <button className="btn btn-primary" onClick={openAddDrawer}>
            Add secret
          </button>
        </CanDo>
      </div>

      <div className="security-notice" role="note">
        🔒 Values are write-only and never returned by the API. Only masked previews are shown.
      </div>

      <div className="filter-tabs" role="tablist" aria-label="Filter by scope">
        {SCOPE_FILTERS.map(f => (
          <button
            key={f.value}
            role="tab"
            aria-selected={scopeFilter === f.value}
            className={`filter-tab ${scopeFilter === f.value ? 'filter-tab--active' : ''}`}
            onClick={() => setScopeFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="skeleton" style={{ height: 200, borderRadius: 8 }} />
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🔑</div>
          <h3>No secrets found</h3>
          <p>Store API keys, tokens, and credentials your agents need at runtime.</p>
          <CanDo permission={Permission.SECRETS_WRITE}>
            <button className="btn btn-primary" onClick={openAddDrawer}>Add secret</button>
          </CanDo>
        </div>
      ) : (
        <div className="secrets-table-wrapper">
          <table className="secrets-table" aria-label="Secrets">
            <thead>
              <tr>
                <th scope="col">Key</th>
                <th scope="col">Value</th>
                <th scope="col">Scope</th>
                <th scope="col">Last updated</th>
                <th scope="col"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(s => <SecretRow key={s.id} secret={s} />)}
            </tbody>
          </table>
        </div>
      )}

      {/* Confirm-delete modal */}
      {confirmDeleteId && (
        <div className="modal-overlay" role="dialog" aria-modal="true"
          aria-label="Confirm deletion">
          <div className="modal modal--danger">
            <h2>Delete secret?</h2>
            <p>This cannot be undone. Any run that references this key will fail.</p>
            <div className="modal-actions">
              <button className="btn" onClick={() => setConfirmDeleteId(null)}>Cancel</button>
              <button className="btn btn-danger"
                onClick={() => { /* handled by useDeleteSecret */
                  setConfirmDeleteId(null);
                }}
              >Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
