/**
 * src/features/security/RiskBadge.tsx
 *
 * Renders a compact chip for `ActionEvent.security_risk` (Stage 3.1).
 * Mirrors HealthBadge's pattern: reuses the shared core `Badge` component
 * and maps enum → BadgeVariant. Hides on UNKNOWN and null/undefined so the
 * event timeline stays clean when no analyzer is attached or the analyzer
 * has no signal for a given action.
 *
 * SecurityRisk enum ground truth: openhands.sdk.security.risk (SDK 1.40.0)
 *   UNKNOWN | LOW | MEDIUM | HIGH
 */
import { Badge, type BadgeVariant } from '@/components/core/Badge';
import type { SecurityRisk } from '@/lib/schemas/event';

const VARIANT_BY_RISK: Record<Exclude<SecurityRisk, 'UNKNOWN'>, BadgeVariant> = {
  LOW:    'success',
  MEDIUM: 'warning',
  HIGH:   'error',
};

const LABEL_BY_RISK: Record<Exclude<SecurityRisk, 'UNKNOWN'>, string> = {
  LOW:    'low risk',
  MEDIUM: 'medium risk',
  HIGH:   'high risk',
};

export interface RiskBadgeProps {
  risk?: SecurityRisk | null;
  className?: string;
}

/**
 * Renders LOW/MEDIUM/HIGH as color-coded chips. Returns null when the risk
 * is UNKNOWN or absent so the event timeline collapses cleanly.
 */
export function RiskBadge({ risk, className }: RiskBadgeProps) {
  if (!risk || risk === 'UNKNOWN') return null;
  const variant = VARIANT_BY_RISK[risk];
  const label = LABEL_BY_RISK[risk];
  return (
    <span role="status" aria-label={`Security risk: ${label}`}>
      <Badge variant={variant} size="sm" className={className}>
        {label}
      </Badge>
    </span>
  );
}
