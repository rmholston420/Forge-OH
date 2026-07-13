'use client';
import type { Settings } from '@/lib/schemas/settings';

const MODELS = [
  { value: 'gpt-4o',            label: 'GPT-4o' },
  { value: 'claude-opus-4',     label: 'Claude Opus 4' },
  { value: 'gemini-2.5-pro',    label: 'Gemini 2.5 Pro' },
  { value: 'local-llama',       label: 'Local (LLaMA)' },
];

interface Props {
  settings: Settings;
  draft: Partial<Settings>;
  agentPresets: { id: string; name: string }[];
  onChange: (patch: Partial<Settings>) => void;
}

export function ModelSection({ settings, draft, agentPresets, onChange }: Props) {
  const current = { ...settings, ...draft };

  return (
    <section aria-labelledby="model-heading">
      <h2 id="model-heading">Model &amp; Agent</h2>

      <div className="settings-field">
        <label htmlFor="defaultModel">Default model</label>
        <select
          id="defaultModel"
          value={current.defaultModel}
          onChange={(e) => onChange({ defaultModel: e.target.value })}
        >
          {MODELS.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
      </div>

      <div className="settings-field">
        <label htmlFor="defaultAgentPreset">Default agent preset</label>
        <select
          id="defaultAgentPreset"
          value={current.defaultAgentPreset}
          onChange={(e) => onChange({ defaultAgentPreset: e.target.value })}
        >
          {agentPresets.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </div>

      <div className="settings-field">
        <label htmlFor="maxConcurrentRuns">Max concurrent runs</label>
        <div className="stepper">
          <button
            type="button"
            aria-label="Decrease"
            disabled={current.maxConcurrentRuns <= 1}
            onClick={() => onChange({ maxConcurrentRuns: current.maxConcurrentRuns - 1 })}
          >−</button>
          <output id="maxConcurrentRuns">{current.maxConcurrentRuns}</output>
          <button
            type="button"
            aria-label="Increase"
            disabled={current.maxConcurrentRuns >= 8}
            onClick={() => onChange({ maxConcurrentRuns: current.maxConcurrentRuns + 1 })}
          >+</button>
        </div>
      </div>

      <div className="settings-field settings-field--toggle">
        <div>
          <label htmlFor="autoApprove">Auto-approve steps</label>
          <p className="settings-field-hint">Runs will proceed without requiring manual approval for each step.</p>
        </div>
        <input
          id="autoApprove"
          type="checkbox"
          role="switch"
          checked={current.autoApprove}
          onChange={(e) => onChange({ autoApprove: e.target.checked })}
        />
      </div>

      {current.autoApprove && (
        <div className="callout callout--warning" role="alert">
          <strong>Warning:</strong> Auto-approve bypasses manual review of agent actions.
          Only enable this if you trust the current agent preset and workspace.
        </div>
      )}

      <div className="settings-field settings-field--toggle">
        <div>
          <label htmlFor="streamingEnabled">Streaming events</label>
          <p className="settings-field-hint">Receive real-time events via Socket.IO during runs.</p>
        </div>
        <input
          id="streamingEnabled"
          type="checkbox"
          role="switch"
          checked={current.streamingEnabled}
          onChange={(e) => onChange({ streamingEnabled: e.target.checked })}
        />
      </div>
    </section>
  );
}
