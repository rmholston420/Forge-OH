'use client';
import { usePresets } from './hooks';
import { useAgentPresetStore } from './store';
import { AgentPresetCard } from './AgentPresetCard';
import { CanDo } from '@/components/auth/CanDo';
import { Permission } from '@/lib/rbac/permissions';

export default function AgentPresetsPage() {
  const { data: presets = [], isLoading } = usePresets();
  const { openCreateDrawer } = useAgentPresetStore();

  return (
    <div className="presets-page">
      <div className="page-header">
        <div>
          <h1>Agent Presets</h1>
          <p className="page-subtitle">
            {presets.length} preset{presets.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        <CanDo permission={Permission.SETTINGS_WRITE}>
          <button className="btn btn-primary" onClick={openCreateDrawer}>
            New preset
          </button>
        </CanDo>
      </div>

      {isLoading ? (
        <div className="preset-grid">
          {[1, 2, 3].map(i => (
            <div key={i} className="skeleton" style={{ height: 180, borderRadius: 8 }} />
          ))}
        </div>
      ) : presets.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🤖</div>
          <h3>No agent presets yet</h3>
          <p>Presets define the model, tools, and guardrails each run uses.</p>
          <CanDo permission={Permission.SETTINGS_WRITE}>
            <button className="btn btn-primary" onClick={openCreateDrawer}>
              Create first preset
            </button>
          </CanDo>
        </div>
      ) : (
        <div className="preset-grid">
          {/* Default preset first */}
          {[...presets].sort((a, b) => (b.isDefault ? 1 : 0) - (a.isDefault ? 1 : 0))
            .map(p => <AgentPresetCard key={p.id} preset={p} />)}
        </div>
      )}
    </div>
  );
}
