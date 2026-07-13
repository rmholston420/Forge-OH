'use client';
import { useState, useEffect } from 'react';
import { useSettings, useUpdateSettings, useResetSettings, useModelRoutingStatus } from '@/features/settings/hooks';
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
  const { data: routingStatus, isLoading: routingLoading, isFetching: routingFetching, refetch: refetchRoutingStatus } = useModelRoutingStatus();
  const { data: presetsData } = useAgentPresets();
  const updateMutation = useUpdateSettings();
  const resetMutation  = useResetSettings();
  const { activeTab, setActiveTab, unsavedChanges, setUnsavedChanges,
          resetConfirmOpen, setResetConfirmOpen } = useSettingsStore();

  const [draft, setDraft] = useState<Partial<Settings>>({});

  function healthBadgeClasses(healthy: boolean) {
    return healthy
      ? 'bg-green-100 text-green-800 border-green-200 dark:bg-green-950/40 dark:text-green-300 dark:border-green-900'
      : 'bg-red-100 text-red-800 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-900';
  }
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
        <section className="rounded-xl border border-black/10 bg-white/60 p-4 shadow-sm dark:border-white/10 dark:bg-white/5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold">Model routing</h2>
              <p className="text-sm text-neutral-600 dark:text-neutral-300">
                Live backend diagnostics for Ollama-first and vLLM-backup routing.
              </p>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2">
              {routingStatus && (
                <>
                  <span className={`inline-flex items-center rounded-full border px-2 py-1 text-xs font-medium ${healthBadgeClasses(routingStatus.ollamaPrimaryHealthy)}`}>
                    Ollama primary: {routingStatus.ollamaPrimaryHealthy ? 'Healthy' : 'Unavailable'}
                  </span>
                  <span className={`inline-flex items-center rounded-full border px-2 py-1 text-xs font-medium ${healthBadgeClasses(routingStatus.ollamaFastHealthy)}`}>
                    Ollama fast: {routingStatus.ollamaFastHealthy ? 'Healthy' : 'Unavailable'}
                  </span>
                  <span className={`inline-flex items-center rounded-full border px-2 py-1 text-xs font-medium ${healthBadgeClasses(routingStatus.vllmHealthy)}`}>
                    vLLM: {routingStatus.vllmHealthy ? 'Healthy' : 'Unavailable'}
                  </span>
                </>
              )}
              <button
                type="button"
                onClick={() => refetchRoutingStatus()}
                className="inline-flex items-center rounded-full border border-black/10 px-3 py-1.5 text-xs font-medium transition hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/10"
                disabled={routingFetching}
              >
                {routingFetching || routingLoading ? 'Refreshing…' : 'Refresh diagnostics'}
              </button>
            </div>
          </div>

          {!routingStatus ? (
            <div className="text-sm text-neutral-600 dark:text-neutral-300">
              Unable to load routing diagnostics.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-lg border border-black/10 p-3 dark:border-white/10">
                  <div className="text-xs uppercase tracking-wide text-neutral-500">Ollama URL</div>
                  <div className="mt-1 text-sm font-medium break-all">{routingStatus.ollamaUrl}</div>
                </div>
                <div className="rounded-lg border border-black/10 p-3 dark:border-white/10">
                  <div className="text-xs uppercase tracking-wide text-neutral-500">vLLM URL</div>
                  <div className="mt-1 text-sm font-medium break-all">{routingStatus.vllmUrl}</div>
                </div>
                <div className="rounded-lg border border-black/10 p-3 dark:border-white/10">
                  <div className="text-xs uppercase tracking-wide text-neutral-500">Primary model</div>
                  <div className="mt-1 text-sm font-medium break-all">{routingStatus.primaryModel}</div>
                </div>
                <div className="rounded-lg border border-black/10 p-3 dark:border-white/10">
                  <div className="text-xs uppercase tracking-wide text-neutral-500">Fast model</div>
                  <div className="mt-1 text-sm font-medium break-all">{routingStatus.fastModel}</div>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-lg border border-black/10 p-3 dark:border-white/10">
                  <div className="text-xs uppercase tracking-wide text-neutral-500">Ollama primary health</div>
                  <div className={`mt-1 text-sm font-semibold ${routingStatus.ollamaPrimaryHealthy ? 'text-green-600' : 'text-red-600'}`}>
                    {routingStatus.ollamaPrimaryHealthy ? 'Healthy' : 'Unavailable'}
                  </div>
                </div>
                <div className="rounded-lg border border-black/10 p-3 dark:border-white/10">
                  <div className="text-xs uppercase tracking-wide text-neutral-500">Ollama fast health</div>
                  <div className={`mt-1 text-sm font-semibold ${routingStatus.ollamaFastHealthy ? 'text-green-600' : 'text-red-600'}`}>
                    {routingStatus.ollamaFastHealthy ? 'Healthy' : 'Unavailable'}
                  </div>
                </div>
                <div className="rounded-lg border border-black/10 p-3 dark:border-white/10">
                  <div className="text-xs uppercase tracking-wide text-neutral-500">vLLM health</div>
                  <div className={`mt-1 text-sm font-semibold ${routingStatus.vllmHealthy ? 'text-green-600' : 'text-red-600'}`}>
                    {routingStatus.vllmHealthy ? 'Healthy' : 'Unavailable'}
                  </div>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-black/10 text-left dark:border-white/10">
                      <th className="px-2 py-2 font-medium">Task</th>
                      <th className="px-2 py-2 font-medium">Context</th>
                      <th className="px-2 py-2 font-medium">Selected</th>
                      <th className="px-2 py-2 font-medium">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {routingStatus.probes.map((probe) => (
                      <tr key={`${probe.taskComplexity}-${probe.contextLength}`} className="border-b border-black/5 dark:border-white/5">
                        <td className="px-2 py-2">{probe.taskComplexity}</td>
                        <td className="px-2 py-2">{probe.contextLength}</td>
                        <td className="px-2 py-2 font-medium">{probe.selected ?? '—'}</td>
                        <td className="px-2 py-2 text-red-600 dark:text-red-400">{probe.error ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>

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
