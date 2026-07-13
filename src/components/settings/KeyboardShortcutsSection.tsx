'use client';
import { useEffect, useRef } from 'react';
import { useSettingsStore } from '@/features/settings/store';
import type { Settings } from '@/lib/schemas/settings';

const ACTION_LABELS: Record<string, string> = {
  newRun:          'New run',
  commandPalette:  'Command palette',
  focusSearch:     'Focus search',
  pauseRun:        'Pause run',
  approveStep:     'Approve step',
};

function formatKeyCombo(e: KeyboardEvent): string {
  const parts: string[] = [];
  if (e.ctrlKey || e.metaKey) parts.push('Ctrl');
  if (e.altKey) parts.push('Alt');
  if (e.shiftKey) parts.push('Shift');
  if (e.key && e.key !== 'Control' && e.key !== 'Alt' && e.key !== 'Shift' && e.key !== 'Meta') {
    parts.push(e.key.length === 1 ? e.key.toUpperCase() : e.key);
  }
  return parts.join('+');
}

interface Props {
  settings: Settings;
  draft: Partial<Settings>;
  onChange: (patch: Partial<Settings>) => void;
}

export function KeyboardShortcutsSection({ settings, draft, onChange }: Props) {
  const current = { ...settings, ...draft };
  const shortcuts = { ...current.keyboardShortcuts };
  const { capturingShortcutFor, setCapturingShortcutFor } = useSettingsStore();
  const captureRef = useRef<string | null>(null);
  captureRef.current = capturingShortcutFor;

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (!captureRef.current) return;
      if (e.key === 'Escape') { setCapturingShortcutFor(null); return; }
      e.preventDefault();
      const combo = formatKeyCombo(e);
      if (!combo) return;
      const action = captureRef.current;
      onChange({ keyboardShortcuts: { ...shortcuts, [action]: combo } });
      setCapturingShortcutFor(null);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [shortcuts, onChange, setCapturingShortcutFor]);

  // Detect conflicts
  const comboCounts: Record<string, number> = {};
  Object.values(shortcuts).forEach((v) => { comboCounts[v] = (comboCounts[v] ?? 0) + 1; });

  return (
    <section aria-labelledby="shortcuts-heading">
      <h2 id="shortcuts-heading">Keyboard shortcuts</h2>
      <p className="settings-section-hint">Click a shortcut to rebind it. Press Escape to cancel.</p>
      <table className="shortcuts-table">
        <thead>
          <tr>
            <th scope="col">Action</th>
            <th scope="col">Shortcut</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(ACTION_LABELS).map(([action, label]) => {
            const combo = shortcuts[action] ?? '—';
            const isCapturing = capturingShortcutFor === action;
            const isConflict = (comboCounts[combo] ?? 0) > 1;
            return (
              <tr key={action}>
                <td>{label}</td>
                <td>
                  <button
                    type="button"
                    className={[
                      'shortcut-key',
                      isCapturing ? 'shortcut-key--capturing' : '',
                      isConflict  ? 'shortcut-key--conflict'  : '',
                    ].join(' ').trim()}
                    onClick={() => setCapturingShortcutFor(isCapturing ? null : action)}
                    aria-label={isCapturing ? `Press keys for ${label}` : `Rebind ${label}: currently ${combo}`}
                    aria-pressed={isCapturing}
                  >
                    {isCapturing ? 'Press keys…' : combo}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
