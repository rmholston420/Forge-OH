import React from 'react';
import type { SecretRef } from '@/features/secrets/schemas';
import { formatRelativeTime } from '@/lib/utils/format';

const SCOPE_COLORS: Record<string, string> = {
  global: 'var(--color-accent-soft)',
  workspace: 'var(--color-state-running)',
  run: 'var(--color-text-muted)',
};

const PROVIDER_LABELS: Record<string, string> = {
  env: 'ENV',
  vault: 'Vault',
  'k8s-secret': 'K8s',
  plaintext: 'Plain',
};

interface SecretRowProps {
  secret: SecretRef;
  onRotate: (id: string) => void;
  onDelete: (id: string) => void;
}

export function SecretRow({ secret, onRotate, onDelete }: SecretRowProps) {
  const { id, name, scope } = secret;
  const provider = 'vault';
  const maskedPreview = secret.key ?? '••••••';
  const createdAt = null;
  const rotatedAt = null;
  const usedIn: string[] = [];

  return (
    <tr className="secret-row">
      <td className="secret-row__name">
        <span className="secret-row__name-text">{name}</span>
      </td>
      <td className="secret-row__value" aria-label="Secret value (masked)">
        {/* Raw value is NEVER shown — only masked preview */}
        <code className="secret-masked">{maskedPreview}</code>
      </td>
      <td>
        <span
          className="badge"
          style={{ color: SCOPE_COLORS[scope] }}
          aria-label={`Scope: ${scope}`}
        >
          {scope}
        </span>
      </td>
      <td>
        <span className="badge badge--secondary" aria-label={`Provider: ${PROVIDER_LABELS[provider]}`}>
          {PROVIDER_LABELS[provider]}
        </span>
      </td>
      <td className="secret-row__meta">
        {usedIn.length > 0 && (
          <span className="badge badge--secondary">{usedIn.length} run{usedIn.length !== 1 ? 's' : ''}</span>
        )}
      </td>
      <td className="secret-row__created">
        <span className="secret-row__date">
          {rotatedAt ? `Rotated ${formatRelativeTime(rotatedAt)}` : (createdAt ? formatRelativeTime(createdAt) : '—')}
        </span>
      </td>
      <td className="secret-row__actions">
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => onRotate(id)}
          aria-label={`Rotate secret ${name}`}
        >
          Rotate
        </button>
        <button
          className="btn btn-ghost btn-sm btn-destructive"
          onClick={() => onDelete(id)}
          aria-label={`Delete secret ${name}`}
        >
          Delete
        </button>
      </td>
    </tr>
  );
}
