'use client';
import { useSetDefaultPreset, useDuplicatePreset, useDeletePreset } from './hooks';
import { useAgentPresetStore } from './store';
import { CanDo } from '@/components/auth/CanDo';
import { Permission } from '@/lib/rbac/permissions';
import type { AgentPreset } from './schemas';

const MODEL_BADGES: Record<string, { label: string; cls: string }> = {
  'gpt-4o':         { label: 'GPT-4o',        cls: 'badge badge--success'  },
  'claude-opus-4':  { label: 'Claude Opus 4', cls: 'badge badge--primary'  },
  'gemini-2.5-pro': { label: 'Gemini 2.5',   cls: 'badge badge--info'     },
  'local-llama':    { label: 'Local LLaMA',  cls: 'badge badge--muted'    },
};

export function AgentPresetCard({ preset }: { preset: AgentPreset }) {
  const setDefault  = useSetDefaultPreset();
  const duplicate   = useDuplicatePreset();
  const del         = useDeletePreset();
  const { openEditDrawer, setConfirmDelete } = useAgentPresetStore();

  const model = MODEL_BADGES[preset.model] ?? { label: preset.model, cls: 'badge badge--muted' };

  return (
    <article
      className={`preset-card ${preset.isDefault ? 'preset-card--default' : ''}`}
      aria-label={preset.name}
    >
      <div className="preset-card-header">
        <div className="preset-card-title">
          <h3>{preset.name}</h3>
          {preset.isDefault && (
            <span className="badge badge--gold" aria-label="Default preset">★ Default</span>
          )}
        </div>
        <span className={model.cls}>{model.label}</span>
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
        <CanDo permission={Permission.SETTINGS_WRITE}>
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
        </CanDo>
      </div>
    </article>
  );
}
