/**
 * src/features/inference-backends/HealthBadge.tsx
 *
 * Reuses the shared `Badge` core component. Health-state → variant map
 * matches the CSS mapping documented in
 * bff/services/inference_backends/types.py::BackendHealth (healthy →
 * success, degraded → warning, unhealthy → error, muted → muted).
 */
import { Badge, type BadgeVariant } from '@/components/core/Badge';
import type { HealthState } from './schemas';

const VARIANT_BY_STATE: Record<HealthState, BadgeVariant> = {
  healthy:   'success',
  degraded:  'warning',
  unhealthy: 'error',
  muted:     'muted',
};

const LABEL_BY_STATE: Record<HealthState, string> = {
  healthy:   'healthy',
  degraded:  'degraded',
  unhealthy: 'unhealthy',
  muted:     'muted',
};

export interface HealthBadgeProps {
  state:     HealthState;
  latencyMs?: number | null;
  className?: string;
}

export function HealthBadge({ state, latencyMs, className }: HealthBadgeProps) {
  const label = latencyMs != null && state !== 'unhealthy'
    ? `${LABEL_BY_STATE[state]} · ${latencyMs}ms`
    : LABEL_BY_STATE[state];
  return (
    <Badge variant={VARIANT_BY_STATE[state]} size="sm" className={className}>
      {label}
    </Badge>
  );
}
