/**
 * src/tests/unit/RiskBadge.test.tsx
 * Covers: RiskBadge SecurityRisk → variant → CSS class mapping,
 * hidden on UNKNOWN/absent.
 */
import React from 'react';
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { RiskBadge } from '@/features/security/RiskBadge';

describe('RiskBadge', () => {
  it('maps LOW → success variant', () => {
    const { container } = render(<RiskBadge risk="LOW" />);
    const badge = container.querySelector('span > span');
    expect(badge).not.toBeNull();
    expect(badge!.className).toMatch(/success/);
  });

  it('maps MEDIUM → warning variant', () => {
    const { container } = render(<RiskBadge risk="MEDIUM" />);
    expect(container.querySelector('span > span')!.className).toMatch(/warning/);
  });

  it('maps HIGH → error variant', () => {
    const { container } = render(<RiskBadge risk="HIGH" />);
    expect(container.querySelector('span > span')!.className).toMatch(/error/);
  });

  it('returns null on UNKNOWN', () => {
    const { container } = render(<RiskBadge risk="UNKNOWN" />);
    expect(container.firstChild).toBeNull();
  });

  it('returns null on undefined', () => {
    const { container } = render(<RiskBadge />);
    expect(container.firstChild).toBeNull();
  });

  it('returns null on null', () => {
    const { container } = render(<RiskBadge risk={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('sets aria-label with human-readable risk', () => {
    const { container } = render(<RiskBadge risk="HIGH" />);
    const wrapper = container.querySelector('span[role="status"]');
    expect(wrapper?.getAttribute('aria-label')).toBe('Security risk: high risk');
  });

  it('renders visible text label', () => {
    const { container } = render(<RiskBadge risk="MEDIUM" />);
    expect(container.textContent).toBe('medium risk');
  });
});
