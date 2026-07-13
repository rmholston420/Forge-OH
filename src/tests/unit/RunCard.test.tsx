import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RunCard } from '@/components/domain/RunCard';
import { mockRuns } from '../fixtures/runs.fixture';

// next/link requires a router — mock it
vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: any) => <a href={href} {...rest}>{children}</a>,
}));

describe('RunCard', () => {
  const run = mockRuns[0];

  it('renders run title', () => {
    render(<RunCard run={run} />);
    expect(screen.getByText(run.title)).toBeTruthy();
  });

  it('renders status badge', () => {
    render(<RunCard run={run} />);
    expect(screen.getByText(run.status.replace(/_/g, ' '))).toBeTruthy();
  });

  it('links to run detail page', () => {
    render(<RunCard run={run} />);
    const link = screen.getByRole('link');
    expect(link.getAttribute('href')).toBe(`/runs/${run.id}`);
  });
});
