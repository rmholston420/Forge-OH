'use client';
import { useRotateSecret, useDeleteSecret } from './hooks';
import { useSecretsStore } from './store';
import { formatDate } from '@/lib/utils/format';
import type { Secret } from './schemas';

const SCOPE_CLASSES: Record<string, string> = {
  global:    'badge badge--primary',
  workspace: 'badge badge--info',
  run:       'badge badge--muted',
};

export function SecretRow({ secret }: { secret: Secret }) {
  const rotate = useRotateSecret();
  const { setConfirmDeleteId } = useSecretsStore();

  return (
    <tr className="secret-row">
      <td className="secret-key" data-testid="secret-key">
        <code>{secret.key}</code>
      </td>
      <td className="secret-value" aria-label="Masked value">
        <span className="masked-value" aria-hidden="true">{'\u2022'.repeat(8)}{secret.maskedValue.slice(-4)}</span>
        <span className="sr-only">Value hidden</span>
      </td>
      <td>
        <span className={SCOPE_CLASSES[secret.scope]}>{secret.scope}</span>
      </td>
      <td className="secret-meta text-muted">
        <span>{secret.createdBy}</span>
        <span className="separator">·</span>
        <time dateTime={secret.updatedAt}>{formatDate(secret.updatedAt)}</time>
      </td>
      <td className="secret-actions">
        <button
            className="btn btn-sm"
            onClick={() =>
              rotate.mutate({ id: secret.id, newValue: prompt('Enter new value') ?? '' })
            }
            disabled={rotate.isPending}
          >
            Rotate
          </button>
          <button
            className="btn btn-sm btn-danger"
            onClick={() => setConfirmDeleteId(secret.id)}
          >
            Delete
          </button>
      </td>
    </tr>
  );
}
