import { beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@/tests/helpers/render';
import { KeyboardShortcutsSection } from '@/components/settings/KeyboardShortcutsSection';
import { SettingsSchema } from '@/lib/schemas/settings';
import { useSettingsStore } from '@/features/settings/store';

const defaults = SettingsSchema.parse({});

// Reset zustand store between tests so capturingShortcutFor from a prior
// test doesn't leak into the next one (the store is a module singleton).
beforeEach(() => {
  useSettingsStore.getState().setCapturingShortcutFor(null);
});

describe('KeyboardShortcutsSection', () => {
  it('renders all action rows', () => {
    render(<KeyboardShortcutsSection settings={defaults} draft={{}} onChange={() => {}} />);
    expect(screen.getByText('New run')).toBeInTheDocument();
    expect(screen.getByText('Command palette')).toBeInTheDocument();
    expect(screen.getByText('Pause run')).toBeInTheDocument();
    expect(screen.getByText('Approve step')).toBeInTheDocument();
  });

  it('enters capture mode on button click', () => {
    render(<KeyboardShortcutsSection settings={defaults} draft={{}} onChange={() => {}} />);
    const rebindBtn = screen.getByRole('button', { name: /Rebind New run/i });
    fireEvent.click(rebindBtn);
    expect(screen.getByText('Press keys\u2026')).toBeInTheDocument();
  });

  it('cancels capture on Escape', () => {
    render(<KeyboardShortcutsSection settings={defaults} draft={{}} onChange={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /Rebind New run/i }));
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByText('Press keys\u2026')).not.toBeInTheDocument();
  });
});
