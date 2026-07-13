import { render, screen, fireEvent } from '@testing-library/react';
import { AppearanceSection } from '@/components/settings/AppearanceSection';
import { SettingsSchema } from '@/lib/schemas/settings';

const defaults = SettingsSchema.parse({});

describe('AppearanceSection', () => {
  it('renders all three theme options', () => {
    render(<AppearanceSection settings={defaults} draft={{}} onChange={() => {}} />);
    expect(screen.getByRole('radio', { name: /System/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Light/i  })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Dark/i   })).toBeInTheDocument();
  });

  it('calls onChange with new theme when radio is clicked', () => {
    const onChange = vi.fn();
    render(<AppearanceSection settings={defaults} draft={{}} onChange={onChange} />);
    fireEvent.click(screen.getByRole('radio', { name: /Dark/i }));
    expect(onChange).toHaveBeenCalledWith({ theme: 'dark' });
  });

  it('renders 6 accent swatches', () => {
    render(<AppearanceSection settings={defaults} draft={{}} onChange={() => {}} />);
    expect(screen.getAllByRole('radio').filter(r =>
      (r as HTMLInputElement).name === 'accentColor'
    )).toHaveLength(6);
  });

  it('shows selected accent color as checked', () => {
    render(<AppearanceSection settings={defaults} draft={{ accentColor: 'blue' }} onChange={() => {}} />);
    const blueRadio = screen.getByRole('radio', { name: /blue/i });
    expect(blueRadio).toBeChecked();
  });
});
