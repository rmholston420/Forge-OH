'use client';
import { useState, useEffect } from 'react';
import { useSettings, useUpdateSettings, useResetSettings } from '@/features/settings/hooks';
import { useSettingsStore } from '@/features/settings/store';
import { useAgentPresets } from '@/features/runs/hooks';
import { AppearanceSection } from '@/components/settings/AppearanceSection';
import { ModelSection } from '@/components/settings/ModelSection';
import { KeyboardShortcutsSection } from '@/components/settings/KeyboardShortcutsSection';
import type { Settings } from '@/lib/schemas/settings';

const TABS = [
  { id: 'appearance', label: 'Appearance' },
  { id: 'model',      label: 'Model & Agent' },
  { id: 'shortcuts',  label: 'Shortcuts' },
  { id: 'about',      label: 'About' },
] as const;

export default function SettingsPage() {
  const { data: settings, isLoading } = useSettings();
  const { data: presetsData } = useAgentPresets();
  const updateMutation = useUpdateSettings();
  const resetMutation  = useResetSettings();
  const { activeTab, setActiveTab, unsavedChanges, setUnsavedChanges,
          resetConfirmOpen, setResetConfirmOpen } = useSettingsStore();

  const [draft, setDraft] = useState<Partial<Settings>>({});
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (unsavedChanges) { e.preventDefault(); e.returnValue = ''; }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [unsavedChanges]);

  function handleChange(patch: Partial<Settings>) {
    setDraft((d) => ({ ...d, ...patch }));
    setUnsavedChanges(true);
  }

  async function handleSave() {
    if (!Object.keys(draft).length) return;
    await updateMutation.mutateAsync(draft);
    setDraft({});
    setUnsavedChanges(false);
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  }

  async function handleReset() {
    await resetMutation.mutateAsync();
    setDraft({});
    setUnsavedChanges(false);
    setResetConfirmOpen(false);
  }

  if (isLoading || !settings) {
    return <div className="settings-skeleton" aria-busy="true" aria-label="Loading settings" />;
  }

  const agentPresets = presetsData ?? [];

  return (
    <div className="settings-layout">
      {/* Vertical tab rail */}
      <nav className="settings-tab-rail" aria-label="Settings sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={activeTab === t.id}
            className={`settings-tab ${activeTab === t.id ? 'settings-tab--active' : ''}`}
            onClick={() => setActiveTab(t.id as any)}
          >
            {t.label}
            {t.id === 'appearance' && unsavedChanges && (
              <span className="unsaved-dot" aria-label="Unsaved changes" />
            )}
          </button>
        ))}
      </nav>

      {/* Content */}
      <main className="settings-content" role="tabpanel">
        {saveSuccess && (
          <div className="toast toast--success" role="status" aria-live="polite">
            Settings saved
          </div>
        )}

        {activeTab === 'appearance' && (
          <AppearanceSection settings={settings} draft={draft} onChange={handleChange} />
        )}
        {activeTab === 'model' && (
          <ModelSection
            settings={settings}
            draft={draft}
            agentPresets={agentPresets}
            onChange={handleChange}
          />
        )}
        {activeTab === 'shortcuts' && (
          <KeyboardShortcutsSection settings={settings} draft={draft} onChange={handleChange} />
        )}
        {activeTab === 'about' && (
          <section aria-labelledby="about-heading">
            <h2 id="about-heading">About Forge-OH</h2>
            <dl className="about-list">
              <dt>Version</dt><dd>0.5.0</dd>
              <dt>OpenHands runtime</dt><dd>Connected</dd>
              <dt>BFF</dt><dd>FastAPI 0.115</dd>
              <dt>Repository</dt>
              <dd><a href="https://github.com/rmholston420/Forge-OH" target="_blank" rel="noopener noreferrer">rmholston420/Forge-OH</a></dd>
            </dl>
          </section>
        )}

        {/* Sticky save/reset footer */}
        <div className="settings-footer">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setResetConfirmOpen(true)}
          >
            Reset to defaults
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!unsavedChanges || updateMutation.isPending}
            onClick={handleSave}
          >
            {updateMutation.isPending ? 'Saving…' : 'Save changes'}
          </button>
        </div>

        {/* Reset confirm dialog */}
        {resetConfirmOpen && (
          <div role="dialog" aria-modal="true" aria-labelledby="reset-dialog-title"
               className="dialog-overlay">
            <div className="dialog">
              <h3 id="reset-dialog-title">Reset all settings?</h3>
              <p>This will restore every setting to its factory default. This cannot be undone.</p>
              <div className="dialog-actions">
                <button type="button" className="btn btn-ghost"
                  onClick={() => setResetConfirmOpen(false)}>Cancel</button>
                <button type="button" className="btn btn-error"
                  onClick={handleReset}
                  disabled={resetMutation.isPending}>
                  {resetMutation.isPending ? 'Resetting…' : 'Reset'}
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
