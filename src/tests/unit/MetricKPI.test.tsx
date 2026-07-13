import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MetricKPI } from '@/components/domain/MetricKPI';

describe('MetricKPI', () => {
  it('renders label and value', () => {
    render(<MetricKPI label="Tokens" value={1234} />);
    expect(screen.getByText('Tokens')).toBeTruthy();
    expect(screen.getByText('1234')).toBeTruthy();
  });

  it('renders unit when provided', () => {
    render(<MetricKPI label="Cost" value="$0.0042" unit="USD" />);
    expect(screen.getByText('USD')).toBeTruthy();
  });

  it('shows skeleton when loading', () => {
    const { container } = render(<MetricKPI label="Tokens" value={0} loading />);
    expect(container.querySelector('[aria-busy="true"]')).toBeTruthy();
  });

  it('renders trend indicator', () => {
    render(<MetricKPI label="Tokens" value={100} trend="up" trendValue="+5%" />);
    expect(screen.getByText(/\+5%/)).toBeTruthy();
  });
});
