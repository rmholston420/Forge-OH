import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { LiveBashPanel } from '@/components/domain/LiveBashPanel';

/**
 * Minimal EventSource stand-in so we can drive the SSE-driven state machine
 * inside useLiveBash without needing a live network SSE server.
 */
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  onerror: ((e: Event) => void) | null = null;
  readyState = 1;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  addEventListener(name: string, fn: (e: MessageEvent) => void): void {
    (this.listeners[name] ??= []).push(fn);
  }
  close(): void {
    this.readyState = 2;
  }
  emit(name: string, data: unknown): void {
    const evt = new MessageEvent(name, { data: JSON.stringify(data) });
    (this.listeners[name] ?? []).forEach((fn) => fn(evt));
  }
}

const originalES = globalThis.EventSource;

beforeEach(() => {
  MockEventSource.instances = [];
  // @ts-expect-error — swapping global for the test
  globalThis.EventSource = MockEventSource;
});
afterEach(() => {
  // @ts-expect-error — restore
  globalThis.EventSource = originalES;
  vi.restoreAllMocks();
});

describe('LiveBashPanel', () => {
  it('renders an idle prompt with the empty-state hint', () => {
    render(<LiveBashPanel runId="r1" />);
    expect(screen.getByTestId('live-bash-input')).toBeInTheDocument();
    expect(screen.getByText(/type a command below/i)).toBeInTheDocument();
    expect(screen.getByText('ready')).toBeInTheDocument();
  });

  it('starts a command and streams output → done on exit_code', async () => {
    server.use(
      http.post('http://localhost:8081/api/runs/r1/bash', async () =>
        HttpResponse.json({
          data: {
            id: 'cmd1',
            kind: 'BashCommand',
            commandId: 'cmd1',
            command: 'echo hi',
            order: 0,
            timestamp: 't0',
            stdout: null,
            stderr: null,
            exitCode: null,
          },
        }),
      ),
    );

    render(<LiveBashPanel runId="r1" />);
    const input = screen.getByTestId('live-bash-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'echo hi' } });
    fireEvent.click(screen.getByTestId('live-bash-run'));

    // wait for status to flip to running (EventSource created)
    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const es = MockEventSource.instances[0];
    expect(es.url).toContain('/api/runs/r1/bash/stream');
    expect(es.url).toContain('command_id=cmd1');

    // Stream stdout, then terminating BashOutput with exit_code=0.
    act(() => {
      es.emit('event', {
        id: 'o1',
        kind: 'BashOutput',
        commandId: 'cmd1',
        order: 1,
        stdout: 'hi\n',
        stderr: null,
        exitCode: null,
        timestamp: 't1',
      });
      es.emit('event', {
        id: 'o2',
        kind: 'BashOutput',
        commandId: 'cmd1',
        order: 2,
        stdout: '',
        stderr: null,
        exitCode: 0,
        timestamp: 't2',
      });
    });

    await waitFor(() =>
      expect(screen.getByText(/done \(exit 0\)/i)).toBeInTheDocument(),
    );
    expect(screen.getByTestId('live-bash-output').textContent).toContain('hi');
    expect(screen.getByTestId('live-bash-output').textContent).toContain(
      '$ echo hi',
    );
    // Stream closed automatically.
    expect(es.readyState).toBe(2);
  });

  it('surfaces an error when startBash fails', async () => {
    server.use(
      http.post('http://localhost:8081/api/runs/r1/bash', async () =>
        HttpResponse.text('boom', { status: 500 }),
      ),
    );

    render(<LiveBashPanel runId="r1" />);
    fireEvent.change(screen.getByTestId('live-bash-input'), {
      target: { value: 'ls' },
    });
    fireEvent.click(screen.getByTestId('live-bash-run'));

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByRole('alert').textContent).toMatch(/500/);
    expect(screen.getByText('error')).toBeInTheDocument();
  });

  it('ignores empty commands', () => {
    render(<LiveBashPanel runId="r1" />);
    fireEvent.click(screen.getByTestId('live-bash-run'));
    expect(MockEventSource.instances.length).toBe(0);
  });
});
