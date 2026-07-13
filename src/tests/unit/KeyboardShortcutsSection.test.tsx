import { render, screen, fireEvent } from '@testing-library/react';
import { KeyboardShortcutsSection } from '@/components/settings/KeyboardShortcutsSection';
import { SettingsSchema } from '@/lib/schemas/settings';

const defaults = SettingsSchema.parse({});

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
