'use client';
import { useSetDefaultPreset, useDuplicatePreset, useDeletePreset } from './hooks';
import { useAgentPresetStore } from './store';
import type { AgentPreset, BackendId } from './schemas';

// Stage 2.1 — presets carry a free-form model string and an optional
// backendId. The model badge shows the runtime family; the backend chip
// shows the routing pin. Both use the shared badge CSS classes.
const BACKEND_BADGES: Record<BackendId, { label: string; cls: string }> = {
  'ollama':       { label: 'Ollama',        cls: 'badge badge--accent'  },
  'vllm-coder':   { label: 'vLLM · coder',   cls: 'badge badge--success' },
  'vllm-planner': { label: 'vLLM · planner', cls: 'badge badge--success' },
  'vllm-legacy':  { label: 'vLLM (legacy)',  cls: 'badge badge--muted'   },
  'llamacpp':     { label: 'llama.cpp',      cls: 'badge badge--muted'   },
  'sglang':       { label: 'SGLang',         cls: 'badge badge--muted'   },
};

// Best-effort family classifier for the model string. Never claims a
// specific backend — the backend chip below carries the truth.
function classifyModel(model: string): { label: string; cls: string } {
  const m = model.toLowerCase();
  if (m.includes('qwen') && m.includes('coder')) return { label: model, cls: 'badge badge--success' };
  if (m.includes('qwen'))                        return { label: model, cls: 'badge badge--success' };
  if (m.includes('deepseek') || m.includes('r1')) return { label: model, cls: 'badge badge--accent' };
  if (m.includes('llama'))                       return { label: model, cls: 'badge badge--accent' };
  if (m.includes('nvfp4') || m.includes('awq') || m.includes('gguf')) {
    return { label: model, cls: 'badge badge--success' };
  }
  return { label: model, cls: 'badge badge--muted' };
}

export function AgentPresetCard({ preset }: { preset: AgentPreset }) {
  const setDefault  = useSetDefaultPreset();
  const duplicate   = useDuplicatePreset();
  const del         = useDeletePreset();
  const { openEditDrawer, setConfirmDelete } = useAgentPresetStore();

  const model   = classifyModel(preset.model);
  const backend = preset.backendId ? BACKEND_BADGES[preset.backendId] : null;

  return (
    <article
      className={`preset-card ${preset.isDefault ? 'preset-card--default' : ''}`}
      aria-label={preset.name}
      data-testid={`preset-card-${preset.id}`}
    >
      <div className="preset-card-header">
        <div className="preset-card-title">
          <h3>{preset.name}</h3>
          {preset.isDefault && (
            <span className="badge badge--gold" aria-label="Default preset">★ Default</span>
          )}
        </div>
        <div className="preset-card-badges" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <span className={model.cls} title={`Model: ${preset.model}`}>{model.label}</span>
          {backend && (
            <span
              className={backend.cls}
              title={`Backend pin: ${preset.backendId}`}
              data-testid={`backend-chip-${preset.backendId}`}
            >
              {backend.label}
            </span>
          )}
          {preset.role && (
            <span className="badge badge--muted" title={`Role hint: ${preset.role}`}>
              role: {preset.role}
            </span>
          )}
        </div>
      </div>

      {preset.description && (
        <p className="preset-card-desc">{preset.description}</p>
      )}

      <div className="preset-card-stats">
        <span title="Max steps">⦭ {preset.maxSteps} steps</span>
        <span title="Max cost">${preset.maxCost.toFixed(2)} max</span>
        <span title="Tools">{preset.toolAllowlist.length} tools</span>
        {preset.loopGuard.enabled && (
          <span title="Loop guard active" className="text-success">🛡️ loop guard</span>
        )}
      </div>

      <div className="preset-card-actions">
        <button className="btn btn-sm" onClick={() => openEditDrawer(preset.id)}>Edit</button>
          <button
            className="btn btn-sm btn-ghost"
            onClick={() => duplicate.mutate(preset.id)}
            disabled={duplicate.isPending}
          >Duplicate</button>
          {!preset.isDefault && (
            <button
              className="btn btn-sm btn-ghost"
              onClick={() => setDefault.mutate(preset.id)}
              disabled={setDefault.isPending}
            >Set default</button>
          )}
          <button
            className="btn btn-sm btn-danger"
            onClick={() => setConfirmDelete(preset.id)}
            disabled={preset.isDefault}
            title={preset.isDefault ? 'Cannot delete the default preset' : 'Delete preset'}
          >Delete</button>
      </div>
    </article>
  );
}
