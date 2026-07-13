'use client';
import { useEffect } from 'react';
import type { Settings } from '@/lib/schemas/settings';

const ACCENT_MAP: Record<string, string> = {
  teal:   '#01696f',
  blue:   '#006494',
  purple: '#7a39bb',
  orange: '#da7101',
  gold:   '#d19900',
  green:  '#437a22',
};

const FONT_SIZE_MAP: Record<string, string> = {
  sm: '14px',
  md: '16px',
  lg: '18px',
};

interface Props {
  settings: Settings;
  draft: Partial<Settings>;
  onChange: (patch: Partial<Settings>) => void;
}

export function AppearanceSection({ settings, draft, onChange }: Props) {
  const current = { ...settings, ...draft };

  // Live-inject CSS variables on draft change
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty('--color-primary', ACCENT_MAP[current.accentColor] ?? ACCENT_MAP.teal);
    root.style.setProperty('--text-base', FONT_SIZE_MAP[current.fontSize] ?? '16px');
  }, [current.accentColor, current.fontSize]);

  return (
    <section aria-labelledby="appearance-heading">
      <h2 id="appearance-heading">Appearance</h2>

      {/* Theme */}
      <fieldset>
        <legend>Theme</legend>
        <div className="theme-cards">
          {(['system', 'light', 'dark'] as const).map((t) => (
            <label key={t} className={`theme-card ${current.theme === t ? 'selected' : ''}`}>
              <input
                type="radio"
                name="theme"
                value={t}
                checked={current.theme === t}
                onChange={() => onChange({ theme: t })}
                className="sr-only"
              />
              <span className="theme-card-preview" data-theme-preview={t} aria-hidden />
              <span>{t.charAt(0).toUpperCase() + t.slice(1)}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {/* Accent color */}
      <fieldset>
        <legend>Accent color</legend>
        <div className="accent-swatches">
          {Object.entries(ACCENT_MAP).map(([name, hex]) => (
            <label key={name} title={name}
              className={`accent-swatch ${current.accentColor === name ? 'selected' : ''}`}>
              <input
                type="radio"
                name="accentColor"
                value={name}
                checked={current.accentColor === name}
                onChange={() => onChange({ accentColor: name as any })}
                className="sr-only"
              />
              <span style={{ background: hex }} aria-hidden />
              <span className="sr-only">{name}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {/* Font size */}
      <fieldset>
        <legend>Font size</legend>
        <div className="font-size-options">
          {(['sm', 'md', 'lg'] as const).map((s) => (
            <label key={s}
              className={`font-size-option ${current.fontSize === s ? 'selected' : ''}`}>
              <input
                type="radio"
                name="fontSize"
                value={s}
                checked={current.fontSize === s}
                onChange={() => onChange({ fontSize: s })}
                className="sr-only"
              />
              <span style={{ fontSize: FONT_SIZE_MAP[s] }}>Aa</span>
              <span>{s.toUpperCase()}</span>
            </label>
          ))}
        </div>
      </fieldset>
    </section>
  );
}
