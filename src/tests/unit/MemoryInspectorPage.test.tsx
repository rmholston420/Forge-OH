/**
 * src/tests/unit/MemoryInspectorPage.test.tsx
 *
 * Stage 5.6a / ADR-024 — asserts the memory-inspector page renders:
 *   - a warning banner when the BFF says the service is unavailable,
 *   - an empty state when the port returns zero records,
 *   - a data table with the projected wire fields when records exist.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import MemoryInspectorPage from '@/features/memory-inspector/MemoryInspectorPage';
import type { MemoryWriteRecord } from '@/features/memory-inspector/schemas';

vi.mock('@/features/memory-inspector/hooks', () => ({
  useRecentMemoryWrites: vi.fn(),
}));

import { useRecentMemoryWrites } from '@/features/memory-inspector/hooks';

function withClient(node: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{node}</QueryClientProvider>;
}

const REC: MemoryWriteRecord = {
  id: 'w-1',
  subject: 'colossus',
  predicate: 'runs',
  object: 'dozerdb',
  provenance: 'agent',
  confidence: 0.9,
  piiTier: 'Public',
  sourceCitation: 'build log',
  writtenAt: '2026-08-06T03:00:00Z',
};

describe('MemoryInspectorPage', () => {
  beforeEach(() => {
    (useRecentMemoryWrites as unknown as ReturnType<typeof vi.fn>).mockReset();
  });

  it('renders warning banner when MemoryPort is unavailable', () => {
    const err = new Error('Memory service unavailable') as Error & { code?: string };
    err.code = 'MEMORY_UNAVAILABLE';
    (useRecentMemoryWrites as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: err,
    });
    render(withClient(<MemoryInspectorPage />));
    expect(screen.getByText(/Memory service unavailable/i)).toBeInTheDocument();
  });

  it('renders empty state when no writes returned', () => {
    (useRecentMemoryWrites as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });
    render(withClient(<MemoryInspectorPage />));
    expect(screen.getByText(/No memory writes yet/i)).toBeInTheDocument();
  });

  it('renders a table row for each record', () => {
    (useRecentMemoryWrites as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [REC],
      isLoading: false,
      error: null,
    });
    render(withClient(<MemoryInspectorPage />));
    expect(screen.getByText('colossus')).toBeInTheDocument();
    expect(screen.getByText('runs')).toBeInTheDocument();
    expect(screen.getByText('dozerdb')).toBeInTheDocument();
    expect(screen.getByText('agent')).toBeInTheDocument();
    expect(screen.getByText('0.90')).toBeInTheDocument();
    expect(screen.getByText('Public')).toBeInTheDocument();
  });

  it('renders a heading and description', () => {
    (useRecentMemoryWrites as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });
    render(withClient(<MemoryInspectorPage />));
    expect(
      screen.getByRole('heading', { name: /memory/i, level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Recent MemoryPort writes/i)).toBeInTheDocument();
  });
});
