/**
 * src/features/run-detail/secrets-hooks.ts
 *
 * TanStack Query mutation for per-run secrets.
 */
import { useMutation } from '@tanstack/react-query';
import { updateRunSecrets } from './secrets-api';

export function useUpdateRunSecrets() {
  return useMutation({
    mutationFn: (vars: { runId: string; secrets: Record<string, string> }) =>
      updateRunSecrets(vars.runId, vars.secrets),
  });
}
