/**
 * src/tests/unit/domain-RunModelSwitchModal.test.tsx
 *
 * Stage 6.5.2 (ADR-027) — RunModelSwitchModal coverage.
 *
 * Uses MSW to stub:
 *   * GET  /api/agent-presets  → the preset list feeding the picker
 *   * POST /api/runs/:id/model → the switch endpoint, exercised for
 *     200 happy, 404 preset-not-found, 422 incompatible-role, 503
 *     model-unavailable to prove each status renders its distinct
 *     user-visible message (ADR-027 error contract).
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { RunModelSwitchModal } from '@/components/domain/RunModelSwitchModal';

const BFF = 'http://localhost:8081';

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const PRESETS = [
  { id: 'ap-1', name: 'Coder (vLLM)', model: 'qwen3-coder-30b-a3b-instruct', role: 'coder', backendId: 'vllm-coder' },
  { id: 'ap-2', name: 'Planner (vLLM)', model: 'qwen3-30b-a3b-thinking-2507', role: 'planner', backendId: 'vllm-planner' },
  { id: 'ap-3', name: 'Coder (Ollama)', model: 'qwen3-coder:30b', role: 'coder', backendId: 'ollama' },
];

function seedPresets() {
  server.use(
    http.get(`${BFF}/api/agent-presets`, () =>
      HttpResponse.json({ data: PRESETS }),
    ),
  );
}

beforeEach(() => {
  server.resetHandlers();
  seedPresets();
});
afterEach(() => vi.restoreAllMocks());

describe('RunModelSwitchModal', () => {
  it('renders modal title and pre-selects the current preset', async () => {
    render(
      <RunModelSwitchModal
        runId="run-1"
        currentAgentPresetId="ap-3"
        open
        onClose={vi.fn()}
      />,
      { wrapper },
    );
    expect(screen.getByRole('heading', { name: /switch model/i })).toBeInTheDocument();
    // Wait for presets to load, then check the select value.
    const select = (await screen.findByLabelText(/target agent preset/i)) as HTMLSelectElement;
    await waitFor(() => expect(select.value).toBe('ap-3'));
  });

  it('Switch button is disabled when the current preset is selected', async () => {
    render(
      <RunModelSwitchModal
        runId="run-1"
        currentAgentPresetId="ap-1"
        open
        onClose={vi.fn()}
      />,
      { wrapper },
    );
    const select = (await screen.findByLabelText(/target agent preset/i)) as HTMLSelectElement;
    await waitFor(() => expect(select.value).toBe('ap-1'));
    const btn = screen.getByRole('button', { name: /switch$/i });
    expect(btn).toBeDisabled();
  });

  it('Cancel closes without calling the mutation', async () => {
    const onClose = vi.fn();
    render(
      <RunModelSwitchModal
        runId="run-1"
        currentAgentPresetId="ap-1"
        open
        onClose={onClose}
      />,
      { wrapper },
    );
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('happy path — 200 fires onSwitched and closes', async () => {
    const onClose = vi.fn();
    const onSwitched = vi.fn();
    server.use(
      http.post(`${BFF}/api/runs/run-1/model`, async ({ request }) => {
        const body = (await request.json()) as { agentPresetId: string };
        expect(body).toEqual({ agentPresetId: 'ap-3' });
        return HttpResponse.json({
          ok: true,
          run_id: 'run-1',
          agentPresetId: 'ap-3',
          resolved: {
            role: 'coder',
            backend: 'ollama',
            model: 'qwen3-coder:30b',
            base_url: 'http://localhost:11434/v1',
            max_tokens: 4096,
          },
          resolved_model_note: null,
        });
      }),
    );
    render(
      <RunModelSwitchModal
        runId="run-1"
        currentAgentPresetId="ap-1"
        open
        onClose={onClose}
        onSwitched={onSwitched}
      />,
      { wrapper },
    );
    const select = (await screen.findByLabelText(/target agent preset/i)) as HTMLSelectElement;
    await waitFor(() => expect(select.value).toBe('ap-1'));
    await userEvent.selectOptions(select, 'ap-3');
    await userEvent.click(screen.getByRole('button', { name: /switch$/i }));
    await waitFor(() => expect(onSwitched).toHaveBeenCalledWith('ap-3'));
    expect(onClose).toHaveBeenCalled();
  });

  it('422 preset_model_incompatible_for_role renders the "Preset misconfigured" banner', async () => {
    server.use(
      http.post(`${BFF}/api/runs/run-1/model`, () =>
        HttpResponse.json(
          {
            code: 'unprocessable_entity',
            detail:
              "preset_model_incompatible_for_role: preset='ap-3' model='foo' role='coder' not in MODEL_ROUTER_CATALOG",
          },
          { status: 422 },
        ),
      ),
    );
    render(
      <RunModelSwitchModal
        runId="run-1"
        currentAgentPresetId="ap-1"
        open
        onClose={vi.fn()}
      />,
      { wrapper },
    );
    const select = (await screen.findByLabelText(/target agent preset/i)) as HTMLSelectElement;
    await waitFor(() => expect(select.value).toBe('ap-1'));
    await userEvent.selectOptions(select, 'ap-3');
    await userEvent.click(screen.getByRole('button', { name: /switch$/i }));
    expect(await screen.findByText(/preset misconfigured/i)).toBeInTheDocument();
    expect(screen.getByText(/MODEL_ROUTER_CATALOG/i)).toBeInTheDocument();
  });

  it('503 model unavailable renders the "Model temporarily unavailable" banner', async () => {
    server.use(
      http.post(`${BFF}/api/runs/run-1/model`, () =>
        HttpResponse.json(
          {
            code: 'service_unavailable',
            detail: "model unavailable for role='coder': no backend can serve",
          },
          { status: 503 },
        ),
      ),
    );
    render(
      <RunModelSwitchModal
        runId="run-1"
        currentAgentPresetId="ap-1"
        open
        onClose={vi.fn()}
      />,
      { wrapper },
    );
    const select = (await screen.findByLabelText(/target agent preset/i)) as HTMLSelectElement;
    await waitFor(() => expect(select.value).toBe('ap-1'));
    await userEvent.selectOptions(select, 'ap-3');
    await userEvent.click(screen.getByRole('button', { name: /switch$/i }));
    expect(await screen.findByText(/model temporarily unavailable/i)).toBeInTheDocument();
  });

  it('404 preset not found renders the "Run or preset not found" banner', async () => {
    server.use(
      http.post(`${BFF}/api/runs/run-1/model`, () =>
        HttpResponse.json(
          { code: 'not_found', detail: 'preset not found: ap-3' },
          { status: 404 },
        ),
      ),
    );
    render(
      <RunModelSwitchModal
        runId="run-1"
        currentAgentPresetId="ap-1"
        open
        onClose={vi.fn()}
      />,
      { wrapper },
    );
    const select = (await screen.findByLabelText(/target agent preset/i)) as HTMLSelectElement;
    await waitFor(() => expect(select.value).toBe('ap-1'));
    await userEvent.selectOptions(select, 'ap-3');
    await userEvent.click(screen.getByRole('button', { name: /switch$/i }));
    expect(await screen.findByText(/run or preset not found/i)).toBeInTheDocument();
    expect(screen.getByText(/no longer exists/i)).toBeInTheDocument();
  });
});
