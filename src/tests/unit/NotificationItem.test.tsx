import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NotificationItem } from '@/components/domain/NotificationItem';
import type { Notification } from '@/lib/schemas/notification';

const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
const wrap = (ui: React.ReactElement) => (
  <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
);

const base: Notification = {
  id:        'aaa-111',
  type:      'info',
  title:     'Test notification',
  body:      'Something happened.',
  read:      false,
  createdAt: new Date().toISOString(),
};

describe('NotificationItem', () => {
  it('renders title and body', () => {
    render(wrap(<NotificationItem notification={base} />));
    expect(screen.getByText('Test notification')).toBeInTheDocument();
    expect(screen.getByText('Something happened.')).toBeInTheDocument();
  });

  it('shows Mark as read button when unread', () => {
    render(wrap(<NotificationItem notification={base} />));
    expect(screen.getByRole('button', { name: /mark as read/i })).toBeInTheDocument();
  });

  it('hides Mark as read button when already read', () => {
    render(wrap(<NotificationItem notification={{ ...base, read: true }} />));
    expect(screen.queryByRole('button', { name: /mark as read/i })).not.toBeInTheDocument();
  });

  it('shows run link when runId present', () => {
    render(wrap(<NotificationItem notification={{ ...base, runId: 'run-xyz' }} />));
    expect(screen.getByRole('link', { name: /view run/i })).toBeInTheDocument();
  });
});
