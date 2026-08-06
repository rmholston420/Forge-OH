/**
 * src/tests/unit/HealthBadge.test.tsx
 * Covers: HealthBadge state → variant → CSS class mapping.
 */
import React from 'react';
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { HealthBadge } from '@/features/inference-backends/HealthBadge';

describe('HealthBadge', () => {
  it('maps healthy → success variant', () => {
    const { container } = render(<HealthBadge state="healthy" />);
    expect(container.querySelector('span')!.className).toMatch(/success/);
  });

  it('maps degraded → warning variant', () => {
    const { container } = render(<HealthBadge state="degraded" />);
    expect(container.querySelector('span')!.className).toMatch(/warning/);
  });

  it('maps unhealthy → error variant', () => {
    const { container } = render(<HealthBadge state="unhealthy" />);
    expect(container.querySelector('span')!.className).toMatch(/error/);
  });

  it('maps muted → muted variant', () => {
    const { container } = render(<HealthBadge state="muted" />);
    expect(container.querySelector('span')!.className).toMatch(/muted/);
  });

  it('renders latency when provided and state is not unhealthy', () => {
    const { container } = render(<HealthBadge state="healthy" latencyMs={42} />);
    expect(container.textContent).toContain('42ms');
  });

  it('does not render latency when state is unhealthy (misleading)', () => {
    const { container } = render(<HealthBadge state="unhealthy" latencyMs={42} />);
    expect(container.textContent).not.toContain('42ms');
  });
});
