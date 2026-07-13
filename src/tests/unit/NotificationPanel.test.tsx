import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NotificationPanel } from '@/components/domain/NotificationPanel';
import { useNotificationsStore } from '@/features/notifications/store';

const server = setupServer(
  http.get('/api/notifications', () => HttpResponse.json([]))
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
const wrap = (ui: React.ReactElement) => (
  <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
);

beforeEach(() => {
  useNotificationsStore.setState({ panelOpen: true, filter: 'all' });
});

describe('NotificationPanel', () => {
  it('renders filter tabs', () => {
    render(wrap(<NotificationPanel />));
    expect(screen.getByRole('tab', { name: /All/i    })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Unread/i })).toBeInTheDocument();
  });

  it('closes on Escape key', () => {
    render(wrap(<NotificationPanel />));
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(useNotificationsStore.getState().panelOpen).toBe(false);
  });
});
