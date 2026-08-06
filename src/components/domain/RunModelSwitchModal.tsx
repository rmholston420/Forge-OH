'use client';
import React, { useMemo, useState } from 'react';
import { Modal } from '@/components/core/Modal';
import { Button } from '@/components/core/Button';
import { Banner } from '@/components/core/Banner';
import { useAgentPresets, useSwitchRunModel } from '@/features/runs/hooks';
import { isApiError } from '@/lib/api/errors';

interface Props {
  runId: string;
  /** The preset currently bound to the run (used to preselect and to avoid a no-op switch). */
  currentAgentPresetId?: string | null;
  open: boolean;
  onClose: () => void;
  /** Fired after a successful switch, before the modal closes. Useful for tests. */
  onSwitched?: (agentPresetId: string) => void;
}

/**
 * Stage 6.5.2 — runtime model-switch modal (ADR-027).
 *
 * The wire contract is PRESET-ONLY. Raw model strings and LLM-Input blobs
 * are rejected at the BFF's Pydantic layer, so this modal only lets the
 * user pick from the AgentPreset registry. Credentials never leave the
 * browser; the BFF hydrates the LLM-Input from the preset + secrets store
 * and forwards to agent-server ``POST /api/conversations/{cid}/switch_llm``.
 *
 * BFF error contract (see bff/routers/runs.py::switch_run_model):
 *   * 404 unknown preset OR unknown run
 *   * 422 preset role=None / empty model / preset_model_incompatible_for_role
 *   * 503 ModelUnavailableError (router can't serve the role right now)
 *   * 502 agent-server 5xx or transport error
 *   * 200 happy — resolved metadata echoed back
 */
export function RunModelSwitchModal({
  runId,
  currentAgentPresetId,
  open,
  onClose,
  onSwitched,
}: Props) {
  const { data: presets, isLoading: presetsLoading, error: presetsError } = useAgentPresets();
  const mut = useSwitchRunModel();

  // Pre-select the current preset if we know it; otherwise fall back to
  // the first entry.  (AgentPresetSchema in features/runs is intentionally
  // loose — no ``isDefault`` field — so we don't try to be clever here.)
  const initialSelection = useMemo(() => {
    if (!presets || presets.length === 0) return '';
    if (currentAgentPresetId && presets.some((p) => p.id === currentAgentPresetId)) {
      return currentAgentPresetId;
    }
    return presets[0].id;
  }, [presets, currentAgentPresetId]);

  const [selected, setSelected] = useState<string>('');
  // Sync the controlled select value when presets finish loading OR when
  // the modal is reopened with a new currentAgentPresetId. We only reset
  // when the modal is actually open to avoid clobbering the user's
  // in-progress selection while the mutation is running.
  React.useEffect(() => {
    if (open && !selected && initialSelection) {
      setSelected(initialSelection);
    }
  }, [open, initialSelection, selected]);

  // Reset the selection when the modal fully closes so the next open
  // starts from the current preset again (not the last picked one).
  React.useEffect(() => {
    if (!open) {
      setSelected('');
      mut.reset();
    }
  }, [open, mut]);

  const handleSwitch = () => {
    if (!selected) return;
    if (selected === currentAgentPresetId) {
      // No-op switch — just close.
      onClose();
      return;
    }
    mut.mutate(
      { runId, agentPresetId: selected },
      {
        onSuccess: () => {
          onSwitched?.(selected);
          onClose();
        },
      },
    );
  };

  const errorMessage = mut.isError ? renderSwitchError(mut.error) : null;

  return (
    <Modal open={open} onClose={onClose} title="Switch model" size="md">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Banner variant="info">
          Switching mid-run replaces the agent&rsquo;s LLM without restarting the
          conversation. The new preset&rsquo;s system prompt and tools do NOT change
          — only the model, base URL, and completion budget swap.
        </Banner>

        {presetsError && (
          <Banner variant="error">
            Failed to load agent presets: {presetsError instanceof Error ? presetsError.message : 'unknown error'}
          </Banner>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label htmlFor="run-model-switch-preset" style={{ fontSize: 13, opacity: 0.8 }}>
            Target agent preset
          </label>
          <select
            id="run-model-switch-preset"
            aria-label="Target agent preset"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            disabled={presetsLoading || mut.isPending || !presets}
            style={{
              padding: '8px 10px',
              borderRadius: 6,
              border: '1px solid var(--border-subtle,#334155)',
              background: 'var(--surface-2,#0b1220)',
              color: 'inherit',
              fontFamily: 'monospace',
            }}
          >
            {presetsLoading && <option value="">Loading…</option>}
            {!presetsLoading && presets && presets.length === 0 && (
              <option value="">No presets available</option>
            )}
            {presets?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.role ? ` · ${p.role}` : ''}
                {p.model ? ` · ${p.model}` : ''}
                {p.id === currentAgentPresetId ? ' (current)' : ''}
              </option>
            ))}
          </select>
        </div>

        {errorMessage && (
          <Banner variant="error" title={errorMessage.title}>
            {errorMessage.body}
          </Banner>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button variant="tertiary" onClick={onClose} disabled={mut.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSwitch}
            disabled={
              mut.isPending ||
              presetsLoading ||
              !selected ||
              selected === currentAgentPresetId
            }
          >
            {mut.isPending ? 'Switching…' : 'Switch'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Error formatting — inspects ApiError.status so 404 / 422 / 503 / 502 each
// render as a distinct user-visible message per ADR-027 error contract.
// ---------------------------------------------------------------------------

function renderSwitchError(err: unknown): { title: string; body: string } {
  if (!isApiError(err)) {
    return {
      title: 'Switch failed',
      body: err instanceof Error ? err.message : 'Unknown error',
    };
  }
  switch (err.status) {
    case 404:
      return {
        title: 'Run or preset not found',
        body: err.message.includes('preset not found')
          ? 'The selected agent preset no longer exists. Reload and try again.'
          : 'This run no longer exists on the agent-server.',
      };
    case 422:
      if (err.message.includes('preset_model_incompatible_for_role')) {
        return {
          title: 'Preset misconfigured',
          body:
            'The selected preset pairs a model with a role it can\u2019t serve ' +
            '(see MODEL_ROUTER_CATALOG). Edit the preset or pick a different one.',
        };
      }
      return {
        title: 'Invalid preset',
        body: err.message,
      };
    case 503:
      return {
        title: 'Model temporarily unavailable',
        body:
          'The router can\u2019t serve this role right now (vLLM offline and no ' +
          'Ollama fallback for this role). Try again shortly.',
      };
    case 502:
      return {
        title: 'Agent-server error',
        body:
          'The BFF forwarded the switch to the agent-server, which returned an ' +
          'error. Check ~/.forge-oh/bff.log for details.',
      };
    default:
      return { title: 'Switch failed', body: err.message };
  }
}

export default RunModelSwitchModal;
